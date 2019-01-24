#!/usr/bin/python3

import os
import logging as log
import sys
from mailustart import convert

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

convert("/unbound.conf", "/etc/unbound/unbound.conf")

os.execv("/usr/sbin/unbound", ["-c /etc/unbound/unbound.conf"])
