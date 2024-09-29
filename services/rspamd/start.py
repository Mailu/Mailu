#!/usr/bin/python3

import os
import glob
import logging as log
import sys
from socrate import system, conf

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

# Actual startup script

os.environ["FRONT_ADDRESS"] = system.resolve_address(os.environ.get("HOST_FRONT", "front"))

if "HOST_REDIS" not in os.environ:
    os.environ["REDIS_ADDRESS"] = system.resolve_address(os.environ.get("HOST_REDIS", "redis"))
os.environ["HOST_ANTIVIRUS"] = system.resolve_address(os.environ.get("HOST_ANTIVIRUS", "antivirus:3310"))

for rspamd_file in glob.glob("/conf/*"):
    conf.jinja(rspamd_file, os.environ, os.path.join("/etc/rspamd/local.d", os.path.basename(rspamd_file)))

# Run rspamd
os.execv("/usr/sbin/rspamd", ["rspamd", "-i", "-f"])
