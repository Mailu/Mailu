#!/usr/bin/python3

import os
import shutil
import logging as log
import sys
import subprocess
from socrate import system, conf

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

# Actual startup script
os.environ["FRONT_ADDRESS"] = system.resolve_address(os.environ.get("HOST_FRONT", "front"))
os.environ["IMAP_ADDRESS"] = system.resolve_address(os.environ.get("HOST_IMAP", "imap"))

os.environ["MAX_FILESIZE"] = str(int(int(os.environ.get("MESSAGE_SIZE_LIMIT"))*0.66/1048576))

base = "/data/_data_/_default_/"
shutil.rmtree(base + "domains/", ignore_errors=True)
os.makedirs(base + "domains", exist_ok=True)
os.makedirs(base + "configs", exist_ok=True)

conf.jinja("/defaults/default.ini", os.environ, "/data/_data_/_default_/domains/default.ini")
conf.jinja("/defaults/application.ini", os.environ, "/data/_data_/_default_/configs/application.ini")
conf.jinja("/defaults/php.ini", os.environ, "/etc/php7/php.ini")

os.system("chown -R nginx:nginx /data")
os.system("chmod -R a+rX /var/www/rainloop/")

subprocess.call(["/config.py"])
os.execv("/usr/sbin/nginx", ["nginx", "-g", "daemon off;"])
