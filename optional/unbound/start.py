#!/usr/bin/env python3

import os
import logging as log
import sys
from socrate import conf, system

system.set_env()

conf.jinja("/unbound.conf", os.environ, "/etc/unbound/unbound.conf")

os.execv("/usr/sbin/unbound", ["unbound", "-c", "/etc/unbound/unbound.conf"])
print('Unbound has terminated. If the container keeps restarting, check the internet connectivity of other containers using for instance "docker compose exec front ping example.com"')
