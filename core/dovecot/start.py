#!/usr/bin/python3

import jinja2
import os
import socket
import glob
import multiprocessing
import tenacity
import logging as log
import sys

from tenacity import retry
from podop import run_server

log.basicConfig(stream=sys.stderr, level=os.environ["LOG_LEVEL"] if "LOG_LEVEL" in os.environ else "WARN")

def start_podop():
    os.setuid(8)
    run_server(0, "dovecot", "/tmp/podop.socket", [
		("quota", "url", "http://admin/internal/dovecot/§"),
		("auth", "url", "http://admin/internal/dovecot/§"),
		("sieve", "url", "http://admin/internal/dovecot/§"),
    ])

convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

@retry(
    stop=tenacity.stop_after_attempt(100),
    wait=tenacity.wait_random(min=2, max=5),
    before=tenacity.before_log(log.getLogger("tenacity.retry"), log.DEBUG),
    before_sleep=tenacity.before_sleep_log(log.getLogger("tenacity.retry"), log.INFO),
    after=tenacity.after_log(log.getLogger("tenacity.retry"), log.DEBUG)
    )
def resolve(hostname):
    logger = log.getLogger("resolve()")
    logger.info(hostname)
    return socket.gethostbyname(hostname)

# Actual startup script
os.environ["FRONT_ADDRESS"] = resolve(os.environ.get("FRONT_ADDRESS", "front"))
os.environ["REDIS_ADDRESS"] = resolve(os.environ.get("REDIS_ADDRESS", "redis"))
if os.environ["WEBMAIL"] != "none":
    os.environ["WEBMAIL_ADDRESS"] = resolve(os.environ.get("WEBMAIL_ADDRESS", "webmail"))

for dovecot_file in glob.glob("/conf/*.conf"):
    convert(dovecot_file, os.path.join("/etc/dovecot", os.path.basename(dovecot_file)))

# Run Podop, then postfix
multiprocessing.Process(target=start_podop).start()
os.system("chown -R mail:mail /mail /var/lib/dovecot /conf")
os.execv("/usr/sbin/dovecot", ["dovecot", "-c", "/etc/dovecot/dovecot.conf", "-F"])
