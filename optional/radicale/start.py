#!/usr/bin/env python3

from socrate import supervisor

supervisor.start([
    {"name": "radicale", "command": ["radicale", "-S", "-C", "/radicale.conf"]},
])
