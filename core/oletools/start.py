#!/usr/bin/env python3

from socrate import system

system.set_env()

with open('/app/olefy.py') as olefy:
    exec(olefy.read())
