#!/usr/bin/env python3

import asyncio

from socrate import system

system.set_env()

# olefy still expects get_event_loop() to create the main-thread loop, which
# Python 3.14 no longer does.
asyncio.set_event_loop(asyncio.new_event_loop())

with open('/app/olefy.py') as olefy:
    exec(olefy.read())
