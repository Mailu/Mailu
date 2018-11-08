#!/usr/bin/python3

import os

# Bootstrap the database if clamav is running for the first time
os.system("[ -f /data/main.cvd ] || freshclam")

# Run the update daemon
os.system("freshclam -d -c 6")

# Run clamav
os.system("clamd")
