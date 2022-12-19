#!/usr/bin/env python3

import os
import logging as log
import sys
from socrate import conf, system

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))
system.set_env()

conf.jinja("/unbound.conf", os.environ, "/etc/unbound/unbound.conf")

os.execv("/usr/sbin/unbound", ["-c /etc/unbound/unbound.conf"])
