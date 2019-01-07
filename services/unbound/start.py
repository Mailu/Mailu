#!/usr/bin/python3

import jinja2
import os
import logging as log
import sys

log.basicConfig(stream=sys.stderr, level=os.environ["LOG_LEVEL"] if "LOG_LEVEL" in os.environ else "WARN")

def convert(src, dst):
    logger = log.getLogger("convert()")
    logger.debug("Source: %s, Destination: %s", src, dst)
    open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

convert("/unbound.conf", "/etc/unbound/unbound.conf")

os.execv("/usr/sbin/unbound", ["-c /etc/unbound/unbound.conf"])
