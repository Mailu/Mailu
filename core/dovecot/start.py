#!/usr/bin/python

import jinja2
import os
import socket
import glob
from tenacity import retry

convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

@retry(stop=stop_after_attempt(10), wait=wait_random(min=2, max=5))
def resolve():
	os.environ["FRONT_ADDRESS"] = socket.gethostbyname(os.environ.get("FRONT_ADDRESS", "front"))
	os.environ["REDIS_ADDRESS"] = socket.gethostbyname(os.environ.get("REDIS_ADDRESS", "redis"))
	if os.environ["WEBMAIL"] != "none":
		os.environ["WEBMAIL_ADDRESS"] = socket.gethostbyname(os.environ.get("WEBMAIL_ADDRESS", "webmail"))

# Actual startup script
resolve()
for dovecot_file in glob.glob("/conf/*"):
    convert(dovecot_file, os.path.join("/etc/dovecot", os.path.basename(dovecot_file)))

# Run postfix
os.system("chown -R mail:mail /mail /var/lib/dovecot")
os.execv("/usr/sbin/dovecot", ["dovecot", "-c", "/etc/dovecot/dovecot.conf", "-F"])
