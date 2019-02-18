#!/usr/bin/python3

import os
import glob
import logging as log
import sys
from mailustart import resolve, convert

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

# Actual startup script
os.environ["FRONT_ADDRESS"] = resolve(os.environ.get("HOST_FRONT", "front"))
os.environ["REDIS_ADDRESS"] = resolve(os.environ.get("HOST_REDIS", "redis"))

for rspamd_file in glob.glob("/conf/*"):
    convert(rspamd_file, os.path.join("/etc/rspamd/local.d", os.path.basename(rspamd_file)))

# Run rspamd
os.execv("/usr/sbin/rspamd", ["rspamd", "-i", "-f"])
