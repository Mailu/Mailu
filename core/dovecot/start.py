#!/usr/bin/python3

import os
import glob
import multiprocessing
import logging as log
import sys
from mailustart import resolve, convert

from podop import run_server

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

def start_podop():
    os.setuid(8)
    url = "http://" + os.environ["ADMIN_ADDRESS"] + "/internal/dovecot/§"
    run_server(0, "dovecot", "/tmp/podop.socket", [
		("quota", "url", url ),
		("auth", "url", url),
		("sieve", "url", url),
    ])

# Actual startup script
os.environ["FRONT_ADDRESS"] = resolve(os.environ.get("FRONT_ADDRESS", "front"))
os.environ["REDIS_ADDRESS"] = resolve(os.environ.get("REDIS_ADDRESS", "redis"))
os.environ["ADMIN_ADDRESS"] = resolve(os.environ.get("ADMIN_ADDRESS", "admin"))
if os.environ["WEBMAIL"] != "none":
    os.environ["WEBMAIL_ADDRESS"] = resolve(os.environ.get("WEBMAIL_ADDRESS", "webmail"))

for dovecot_file in glob.glob("/conf/*.conf"):
    convert(dovecot_file, os.path.join("/etc/dovecot", os.path.basename(dovecot_file)))

# Run Podop, then postfix
multiprocessing.Process(target=start_podop).start()
os.system("chown mail:mail /mail")
os.system("chown -R mail:mail /var/lib/dovecot /conf")
os.execv("/usr/sbin/dovecot", ["dovecot", "-c", "/etc/dovecot/dovecot.conf", "-F"])
