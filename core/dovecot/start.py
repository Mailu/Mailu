#!/usr/bin/python3

import jinja2
import os
import socket
import glob
import multiprocessing
import tenacity

from tenacity import retry
from podop import run_server


def start_podop():
    os.setuid(8)
    run_server(3 if "DEBUG" in os.environ else 0, "dovecot", "/tmp/podop.socket", [
		("quota", "url", "http://admin/internal/dovecot/§"),
		("auth", "url", "http://admin/internal/dovecot/§"),
		("sieve", "url", "http://admin/internal/dovecot/§"),
    ])

convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

@retry(stop=tenacity.stop_after_attempt(100), wait=tenacity.wait_random(min=2, max=5))
def resolve():
	os.environ["FRONT_ADDRESS"] = socket.gethostbyname(os.environ.get("FRONT_ADDRESS", "front"))
	os.environ["REDIS_ADDRESS"] = socket.gethostbyname(os.environ.get("REDIS_ADDRESS", "redis"))
	if os.environ["WEBMAIL"] != "none":
		os.environ["WEBMAIL_ADDRESS"] = socket.gethostbyname(os.environ.get("WEBMAIL_ADDRESS", "webmail"))

# Actual startup script
resolve()

for dovecot_file in glob.glob("/conf/*.conf"):
    convert(dovecot_file, os.path.join("/etc/dovecot", os.path.basename(dovecot_file)))

# Run Podop, then postfix
multiprocessing.Process(target=start_podop).start()
os.system("chown -R mail:mail /mail /var/lib/dovecot /conf")
os.execv("/usr/sbin/dovecot", ["dovecot", "-c", "/etc/dovecot/dovecot.conf", "-F"])
