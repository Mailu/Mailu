#!/usr/bin/python3

import os
import glob
import logging as log
import sys
from socrate import system, conf

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

# Actual startup script

os.environ["FRONT_ADDRESS"] = system.get_host_address_from_environment("FRONT", "front")
os.environ["REDIS_ADDRESS"] = system.get_host_address_from_environment("REDIS", "redis")

if os.environ.get("ANTIVIRUS") == 'clamav':
    os.environ["ANTIVIRUS_ADDRESS"] = system.get_host_address_from_environment("ANTIVIRUS", "antivirus:3310")

for rspamd_file in glob.glob("/conf/*"):
    conf.jinja(rspamd_file, os.environ, os.path.join("/etc/rspamd/local.d", os.path.basename(rspamd_file)))

# Run rspamd
os.execv("/usr/bin/rspamd", ["rspamd", "-i", "-f"])
