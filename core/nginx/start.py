#!/usr/bin/python

import os
import subprocess


if os.environ["TLS_FLAVOR"] == "letsencrypt":
    subprocess.Popen(["/letsencrypt.py"])

subprocess.call(["/config.py"])
os.execv("/usr/sbin/nginx", ["nginx", "-g", "daemon off;"])
