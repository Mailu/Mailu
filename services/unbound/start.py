#!/usr/bin/python3

import os
import logging as log
import sys
from socrate import conf

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

conf.jinja("/unbound.conf", os.environ, "/etc/unbound/unbound.conf")

os.execv("/usr/sbin/unbound", ["-c /etc/unbound/unbound.conf"])
