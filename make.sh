#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
VENV_PATH="${SCRIPT_DIR}/crawler_venv"
TMP_PATH="/tmp"

source "${VENV_PATH}/bin/activate"
scp "nas:~/sssb_feed.xml" "${TMP_PATH}/sssb_feed.xml"
python3 "${SCRIPT_DIR}/sssb.py" "${TMP_PATH}/sssb_feed.xml"
if [ $? != 0 ]; then
	notify-send "Failed to crawl SSSB"
else
	scp "${TMP_PATH}/sssb_feed.xml" "nas:~/sssb_feed.xml"
	notify-send "Successfully updated SSSB RSS feed"
fi
deactivate
