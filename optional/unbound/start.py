#!/usr/bin/env python3

import os
import logging as log
import sys
from socrate import conf, system

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

with open( '/etc/resolv.conf', 'r' ) as resolv:
    for line in resolv.readlines():
        if line.startswith('nameserver '):
            os.environ['DOCKER_RESOLVER'] = line.split(' ')[1].rstrip()
            break

container_names=[]
for key in os.environ:
    if key.endswith('_ADDRESS'):
        container_names.append(os.environ[key])
os.environ['CONTAINERS'] = ','.join(container_names)

conf.jinja("/unbound.conf", os.environ, "/etc/unbound/unbound.conf")

os.execv("/usr/sbin/unbound", ["-c /etc/unbound/unbound.conf"])
