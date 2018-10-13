#!/usr/bin/python

import os
import time
import subprocess


command = [
    "logrotate"
    "/etc/logrotate"
]

# Run logrotate every day
while True:
#    time.sleep(86400)
# Test value
    time.sleep(60)
    subprocess.call(command)
