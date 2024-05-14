from datetime import datetime
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import argparse
import sys

from bs4 import BeautifulSoup
from jinja2 import Template
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def crawl() -> BeautifulSoup:
    opts = Options()
    test_ua = "Mozilla/5.0 (Windows NT 4.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2049.0 Safari/537.36"
    opts.add_argument("--headless")
    opts.add_argument(f"--user-agent={test_ua}")
    opts.binary_location = "/usr/bin/google-chrome"
    driver = webdriver.Chrome(opts)
    driver.get(
        "https://sssb.se/soka-bostad/sok-ledigt/lediga-bostader/"
        "?pagination=0&paginationantal=50"
    )
    return BeautifulSoup(driver.page_source, features="lxml")


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
    return html.strip().replace("\xa0", "")


def get_listing_id(link: str) -> str:
    return parse_qs(urlparse(link).query)["refid"][0]


def parse_rows(soup: BeautifulSoup) -> dict[str, Listing]:
    rows = soup.find_all(class_="ObjektListItem")
    if rows is None:
        raise ValueError("ERROR: couldn't find any rows to parse")
    listings: dict[str, Listing] = {}
    for row in rows:
        link: str = row.find(class_="ObjektTyp").contents[0].attrs["href"]
        img_link: str = row.find(class_="ObjektBild").attrs["src"]
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

    ET.ElementTree(rss).write(
        xml_filepath, encoding="utf-8", xml_declaration=True
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("feed_filepath")
    args = parser.parse_args()

    parsed_rows = {}
    for _ in range(5):
        parsed_rows = parse_rows(crawl())
        if len(parsed_rows) != 0:
            break
    if len(parsed_rows) == 0:
        sys.exit(1)
    create_xml(parsed_rows, Path(args.feed_filepath))
