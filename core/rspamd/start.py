#!/usr/bin/env python3

import os
import glob
import logging as log
import requests
import sys
import time
from socrate import system,conf

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))
system.set_env()

# Actual startup script

for rspamd_file in glob.glob("/conf/*"):
    conf.jinja(rspamd_file, os.environ, os.path.join("/etc/rspamd/local.d", os.path.basename(rspamd_file)))

# Admin may not be up just yet
healthcheck = f'http://{os.environ["ADMIN_ADDRESS"]}/internal/rspamd/local_domains'
while True:
    time.sleep(1)
    try:
        if requests.get(healthcheck,timeout=2).ok:
            break
    except:
        pass
    log.warning("Admin is not up just yet, retrying in 1 second")

# Run rspamd
os.system("mkdir -m 755 -p /run/rspamd")
os.system("chown rspamd:rspamd /run/rspamd")
os.system("find /var/lib/rspamd | grep -v /filter | xargs -n1 chown rspamd:rspamd")
os.execv("/usr/sbin/rspamd", ["rspamd", "-f", "-u", "rspamd", "-g", "rspamd"])
