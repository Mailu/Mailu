#!/usr/bin/python

import jinja2
import os
import socket
import glob
import time

convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

# Actual startup script
i = 0
t = 10
while True:
	i += 1
	try:
		os.environ["FRONT_ADDRESS"] = socket.gethostbyname(os.environ.get("FRONT_ADDRESS", "front"))
	except socket.gaierror as err:
		if i >= t:
			raise
		time.sleep(10)
		continue
	break
if "HOST_REDIS" not in os.environ: os.environ["HOST_REDIS"] = "redis"

for rspamd_file in glob.glob("/conf/*"):
    convert(rspamd_file, os.path.join("/etc/rspamd/local.d", os.path.basename(rspamd_file)))

# Run rspamd
os.execv("/usr/sbin/rspamd", ["rspamd", "-i", "-f"])
