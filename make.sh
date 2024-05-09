#!/bin/bash
source crawler_venv/bin/activate
scp nas:~/sssb_feed.xml /tmp/sssb_feed.xml
python3 sssb.py /tmp/sssb_feed.xml
if [ $? != 0 ]; then
	notify-send "Failed to crawl SSSB"
else
	scp /tmp/sssb_feed.xml nas:~/sssb_feed.xml
	notify-send "Successfully updated SSSB RSS feed"
fi
deactivate
