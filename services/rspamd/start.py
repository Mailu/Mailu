#!/usr/bin/python

import jinja2
import os
import socket
import glob
import tenacity
from tenacity import retry

convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

@retry(stop=tenacity.stop_after_attempt(100), wait=tenacity.wait_random(min=2, max=5))
def resolve():
	os.environ["FRONT_ADDRESS"] = socket.gethostbyname(os.environ.get("FRONT_ADDRESS", "front"))

# Actual startup script
resolve()
if "HOST_REDIS" not in os.environ: os.environ["HOST_REDIS"] = "redis"

for rspamd_file in glob.glob("/conf/*"):
    convert(rspamd_file, os.path.join("/etc/rspamd/local.d", os.path.basename(rspamd_file)))

# Run rspamd
os.execv("/usr/sbin/rspamd", ["rspamd", "-i", "-f"])
