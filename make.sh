#!/bin/bash
VENV_PATH="crawler_venv"
TMP_PATH="/tmp"

source "${VENV_PATH}/bin/activate"
scp "nas:~/sssb_feed.xml" "${TMP_PATH}/sssb_feed.xml"
python3 "sssb.py" "${TMP_PATH}/sssb_feed.xml"
if [ $? != 0 ]; then
	notify-send "Failed to crawl SSSB"
else
	scp "${TMP_PATH}sssb_feed.xml" "nas:~/sssb_feed.xml"
	notify-send "Successfully updated SSSB RSS feed"
fi
deactivate
