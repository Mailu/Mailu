#!/usr/bin/env python3

import os
import logging as log
import sys
from socrate import conf, system

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

env = os.environ.copy()
with open( '/etc/resolv.conf', 'r' ) as resolv:
    for line in resolv.readlines():
        if line.startswith('nameserver '):
            env['DOCKER_RESOLVER'] = line.split(' ')[1].rstrip()
            break

env['CONTAINERS'] = [value for key, value in env.items() if key.endswith('_ADDRESS')]

if not env.get('SUBNET'):
    env['SUBNET'] = system.get_network_v4()

conf.jinja("/unbound.conf", env, "/etc/unbound/unbound.conf")

os.execv("/usr/sbin/unbound", ["-c /etc/unbound/unbound.conf"])
