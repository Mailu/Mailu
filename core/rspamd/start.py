#!/usr/bin/env python3

import os
import glob
import logging as log
import requests
import shutil
import sys
import time
from socrate import system,conf

env = system.set_env()

# Actual startup script

config_files = []
for rspamd_file in glob.glob("/conf/*"):
    conf.jinja(rspamd_file, env, os.path.join("/etc/rspamd/local.d", os.path.basename(rspamd_file)))
    if rspamd_file != '/conf/forbidden_file_extension.map':
        config_files.append(os.path.basename(rspamd_file))

for override_file in glob.glob("/overrides/*"):
    if os.path.basename(override_file) not in config_files:
        shutil.copyfile(override_file, os.path.join("/etc/rspamd/local.d", os.path.basename(override_file)))

# Admin may not be up just yet
healthcheck = f'http://{env["ADMIN_ADDRESS"]}:8080/internal/rspamd/local_domains'
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
os.execv("/usr/bin/rspamd", ["rspamd", "-f", "-u", "rspamd", "-g", "rspamd"])
