#!/usr/bin/env python3

import os
import subprocess

# Check if a stale pid file exists
if os.path.exists("/var/run/nginx.pid"):
    os.remove("/var/run/nginx.pid")

if os.environ["TLS_FLAVOR"] in [ "letsencrypt","mail-letsencrypt" ]:
    subprocess.Popen(["/letsencrypt.py"])
elif os.environ["TLS_FLAVOR"] in [ "mail", "cert" ]:
    subprocess.Popen(["/certwatcher.py"])

subprocess.call(["/config.py"])
os.execv("/usr/sbin/nginx", ["nginx", "-g", "daemon off;"])
