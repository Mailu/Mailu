#!/usr/bin/env python3

import os
import glob
import logging as log
import sys
from socrate import system, conf

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

# Actual startup script

os.environ["REDIS_ADDRESS"] = system.get_host_address_from_environment("REDIS", "redis")
os.environ["ADMIN_ADDRESS"] = system.get_host_address_from_environment("ADMIN", "admin")

if os.environ.get("ANTIVIRUS") == 'clamav':
    os.environ["ANTIVIRUS_ADDRESS"] = system.get_host_address_from_environment("ANTIVIRUS", "antivirus:3310")

for rspamd_file in glob.glob("/conf/*"):
    conf.jinja(rspamd_file, os.environ, os.path.join("/etc/rspamd/local.d", os.path.basename(rspamd_file)))

# Run rspamd
os.execv("/usr/sbin/rspamd", ["rspamd", "-i", "-f"])
