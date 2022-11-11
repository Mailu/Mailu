#!/usr/bin/env python3

import os
import logging as log
import sys

from socrate import system, conf

args = os.environ.copy()

log.basicConfig(stream=sys.stderr, level=args.get("LOG_LEVEL", "WARNING"))

# Build final configuration paths
conf.jinja("/config/nginx-snappymail.conf", args, "/etc/nginx/http.d/snappymail.conf")
if os.path.exists("/var/run/nginx.pid"):
    os.system("nginx -s reload")
