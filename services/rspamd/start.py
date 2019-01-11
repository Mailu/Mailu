#!/usr/bin/python3

import jinja2
import os
import socket
import glob
import tenacity
import logging as log
import sys

from tenacity import retry

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

def convert(src, dst):
    logger = log.getLogger("convert()")
    logger.debug("Source: %s, Destination: %s", src, dst)
    open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

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

if "HOST_REDIS" not in os.environ: os.environ["HOST_REDIS"] = "redis"

for rspamd_file in glob.glob("/conf/*"):
    convert(rspamd_file, os.path.join("/etc/rspamd/local.d", os.path.basename(rspamd_file)))

# Run rspamd
os.execv("/usr/sbin/rspamd", ["rspamd", "-i", "-f"])
