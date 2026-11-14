#!/usr/bin/env python3

from socrate import supervisor

supervisor.start([
    {"name": "fetchmail", "command": ["python3", "/fetchmail.py"]},
])
