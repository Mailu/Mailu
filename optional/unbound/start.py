#!/usr/bin/env python3

import os
import logging as log
import pwd
import subprocess
import sys
from socrate import conf, system

system.set_env()

anchor = "/etc/unbound/trusted-key.key"
result = subprocess.run(["/usr/sbin/unbound-anchor", "-a", anchor], check=False)
if result.returncode:
    log.warning("Unable to refresh the DNSSEC trust anchor (exit status %s)", result.returncode)
if os.path.exists(anchor):
    unbound = pwd.getpwnam("unbound")
    os.chown(anchor, unbound.pw_uid, unbound.pw_gid)

conf.jinja("/unbound.conf", os.environ, "/etc/unbound/unbound.conf")

os.execv("/usr/sbin/unbound", ["unbound", "-c", "/etc/unbound/unbound.conf"])
print('Unbound has terminated. If the container keeps restarting, check the internet connectivity of other containers using for instance "docker compose exec front ping example.com"')
