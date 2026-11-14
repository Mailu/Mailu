#!/usr/bin/env python3

from socrate import supervisor

supervisor.start([
    {"name": "idle", "command": ["/bin/sleep", "infinity"]},
])
