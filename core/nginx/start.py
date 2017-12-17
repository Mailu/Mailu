#!/usr/bin/python

import os
import subprocess

# Check if a stale pid file exists
if os.path.exists("/var/log/nginx.pid"):
    os.remove("/var/log/nginx.pid")

if os.environ["TLS_FLAVOR"] == "letsencrypt":
    subprocess.Popen(["/letsencrypt.py"])

subprocess.call(["/config.py"])
os.execv("/usr/sbin/nginx", ["nginx", "-g", "daemon off;"])
