from datetime import datetime
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import argparse
import sys
import json
from bs4 import BeautifulSoup
from jinja2 import Template
import requests
import os

URL = "https://sssb.se/widgets/?callback=jQuery172034230436949903253_1718622405234&widgets%5B%5D=alert&widgets%5B%5D=objektsummering%40lagenheter&widgets%5B%5D=objektfilter%40lagenheter&widgets%5B%5D=objektsortering%40lagenheter&widgets%5B%5D=objektlistabilder%40lagenheter&widgets%5B%5D=pagineringantal%40lagenheter&widgets%5B%5D=paginering%40lagenheter&widgets%5B%5D=pagineringgofirst%40lagenheter&widgets%5B%5D=pagineringgonew%40lagenheter&widgets%5B%5D=pagineringlista%40lagenheter&widgets%5B%5D=pagineringgoold%40lagenheter&widgets%5B%5D=pagineringgolast%40lagenheter"


def crawl(url_filename: str) -> BeautifulSoup:
    """given a string to a file containing sssb url, return bs parser"""
    response = requests.get(URL, verify=False)
    if response.status_code != 200:
        raise ValueError("request error code")
    # since the response is wrapped in a jquery function call,
    # we need to remove the initial function name and subsequent parentheses.
    start_idx = response.text.find("(") + 1
    end_idx = len(response.text) - 2
    content = json.loads(response.text[start_idx:end_idx])
    html = BeautifulSoup(
        content["html"]["objektlistabilder@lagenheter"], features="lxml"
    )
    return html


@dataclass
class Listing:
    link: str
    img_link: str
    area: str
    address: str
    apt_type: str
    floor: str
    sqm: str
    rent: str
    date: str
    queue_days: str


def strip_html(html: str) -> str:
    """strips html of certain unwanted characters"""
    return html.strip().replace("\xa0", "")


def get_listing_id(link: str) -> str:
    """given a link returns the reference id to that apartment listing"""
    return parse_qs(urlparse(link).query)["refid"][0]


def parse_rows(soup: BeautifulSoup) -> dict[str, Listing]:
    """given bs4 html returns a formatted dictionary from apartment listing
    reference id to structured information about that apartment, i.e. rent,
    floor etc."""
    rows = soup.find_all(class_="ObjektListItem")
    if rows is None:
        raise ValueError("ERROR: couldn't find any rows to parse")
    listings: dict[str, Listing] = {}
    for row in rows:
        link: str = row.find(class_="ObjektTyp").contents[0].attrs["href"]
        img_link: str = row.find(class_="ObjektBild").attrs["data-src"]
        listing_id: str = get_listing_id(link)
        listings[listing_id] = Listing(
            link,
            img_link,
            strip_html(row.find_all(class_="ObjektOmrade")[1].text),
            strip_html(row.find(class_="ObjektAdress").text),
            strip_html(row.find(class_="ObjektTyp").text),
            strip_html(row.find_all(class_="ObjektVaning")[1].text),
            strip_html(row.find_all(class_="ObjektYta")[1].text),
            strip_html(row.find_all(class_="ObjektHyra")[1].text),
            strip_html(row.find_all(class_="ObjektInflytt")[1].text),
            strip_html(row.find_all(class_="ObjektAntalIntresse")[1].text),
        )
    return listings


def generate_post_html(listing: Listing) -> str:
    """given a Listing object returns rendered html for that object"""
    template_str = """
    <img src={{ listing.img_link }}>
    <ul>
        <li> Area: {{ listing.area }}</li>
        <li> Adress: {{ listing.address }}</li>
        <li> Apt. Type: {{ listing.apt_type }}</li>
        <li> Floor: {{ listing.floor }}</li>
        <li> Sq.M: {{ listing.sqm }}</li>
        <li> Rent: {{ listing.rent }}</li>
        <li> Date: {{ listing.date }}</li>
        <li> Queue Days: {{ listing.queue_days }}</li>
    </ul>
    """
    return Template(template_str).render(listing=listing)


def create_xml(listings: dict[str, Listing], xml_filepath: Path) -> None:
    """given a list of apartment listings, converts that to a RSS-compatible
    RSS-file and exports it to the path provided"""
    rss = ET.Element("rss")
    rss.set("version", "2.0")
    channel = ET.SubElement(rss, "channel")
    rss_title = ET.SubElement(channel, "title")
    rss_title.text = "SSSB Apartment Listings"
    rss_link = ET.SubElement(channel, "link")
    rss_link.text = "https://sssb.se"
    rss_desc = ET.SubElement(channel, "description")
    rss_desc.text = "SSSB Apartment Listings"

    rss_img = ET.SubElement(channel, "image")
    rss_img_url = ET.SubElement(rss_img, "url")
    rss_img_url.text = (
        "https://sssb.se/wp-content/uploads/cropped-SSSB-favicon-1-150x150.png"
    )
    rss_img_title = ET.SubElement(rss_img, "title")
    rss_img_title.text = "SSSB Apartment Listings"
    rss_img_link = ET.SubElement(rss_img, "link")
    rss_img_link.text = "https://sssb.se"

    if xml_filepath.exists():
        prev_channel = ET.parse(xml_filepath).find("channel")
        if prev_channel is not None and prev_channel.find("item") is not None:
            for item in prev_channel.iter("item"):
                channel.append(item)

    prev_items = list(channel.iter("item"))
    prev_idx = []
    for item in prev_items:
        item_link = item.find("link")
        if item_link is not None:
            prev_idx.append(get_listing_id(str(item_link.text)))
    for listing_id, listing in listings.items():
        if listing_id in prev_idx:
            continue
        item = ET.SubElement(channel, "item")
        title = ET.SubElement(item, "title")
        title.text = f"{listing.area}; {listing.apt_type}"
        description = ET.SubElement(item, "description")
        description.text = generate_post_html(listing)
        link = ET.SubElement(item, "link")
        link.text = listing.link
        pub_date = ET.SubElement(item, "pubDate")
        pub_date.text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

    ET.ElementTree(rss).write(xml_filepath, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("feed_filepath", help="location of existing/new feed file")
    args = parser.parse_args()

    parsed_rows = {}
    # rudimentary approach to try several times before failure
    for _ in range(5):
        parsed_rows = parse_rows(crawl("url"))
        if len(parsed_rows) != 0:
            break
    if len(parsed_rows) == 0:
        print("ERROR: failed to crawl SSSB")
        sys.exit(1)
    create_xml(parsed_rows, Path(args.feed_filepath))
