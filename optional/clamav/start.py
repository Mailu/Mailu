#!/usr/bin/env python3

import os
import logging as log
import sys

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))
logger=log.getLogger(__name__)

# Bootstrap the database if clamav is running for the first time
if not os.path.isfile("/data/main.cvd"):
    logger.info("Starting primary virus DB download")
    os.system("freshclam")

# Run the update daemon
logger.info("Starting the update daemon")
os.system("freshclam -d -c 6")

# Run clamav
logger.info("Starting clamav")
os.system("clamd")
