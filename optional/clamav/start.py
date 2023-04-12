#!/usr/bin/env python3

import os
import logging as logger
import sys
from socrate import system

system.set_env(log_filters=r'SelfCheck: Database status OK\.$')

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
