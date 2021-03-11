#!/usr/bin/python3

import os
import logging as log
import sys

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))
logger = log.getLogger(__name__)

# Clamav is run for testing. Use a static database.
if os.environ.get("TESTING") and os.path.isfile("/data/testing.cvd"):
    os.system("mv /data/testing.cvd /data/main.cvd")
    log.info("TESTING mode, use static test database.")

# Clamav is not run for testing. Clean up test database.
elif os.path.isfile("/data/testing.cvd"):
    os.system("rm /data/testing.cvd")
    log.info("Normal mode. Remove test database")

# Bootstrap the database if clamav is running for the first time
if not os.path.isfile("/data/main.cvd"):
    logger.info("Starting primary virus DB download")
    os.system("freshclam")

# If Clamav is run for testing, do not download the Clamav DB to prevent HTTP 429 too many requests.
if not os.environ.get("TESTING"):
    # Run the update daemon
    logger.info("Starting the update daemon")
    os.system("freshclam -d -c 6")

# Run clamav
logger.info("Starting clamav")
os.system("clamd")
