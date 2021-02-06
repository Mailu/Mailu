#!/usr/bin/python3

import os
import shutil
import logging as log
import sys
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

conf.jinja("/default.ini", os.environ, "/data/_data_/_default_/domains/default.ini")
conf.jinja("/application.ini", os.environ, "/data/_data_/_default_/configs/application.ini")
conf.jinja("/php.ini", os.environ, "/usr/local/etc/php/conf.d/rainloop.ini")

os.system("chown -R www-data:www-data /data")
os.system("chmod -R a+rX /var/www/html/")

os.execv("/usr/local/bin/apache2-foreground", ["apache2-foreground"])

