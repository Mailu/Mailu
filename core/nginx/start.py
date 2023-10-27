#!/usr/bin/env python3

import os
import subprocess
from socrate import system

system.set_env(log_filters=r'could not be resolved \(\d\: [^\)]+\) while in resolving client address, client\: [^,]+, server: [^\:]+\:(25|110|143|587|465|993|995)$')

# Check if a stale pid file exists
if os.path.exists("/var/run/nginx.pid"):
    os.remove("/var/run/nginx.pid")

if os.environ["TLS_FLAVOR"] in [ "letsencrypt","mail-letsencrypt" ]:
    subprocess.Popen(["/letsencrypt.py"])
elif os.environ["TLS_FLAVOR"] in [ "mail", "cert" ]:
    subprocess.Popen(["/certwatcher.py"])

subprocess.call(["/config.py"])
os.system("dovecot -c /etc/dovecot/proxy.conf")
cmd = ['/usr/sbin/nginx', '-g', 'daemon off;']
system.run_process_and_forward_output(cmd)
