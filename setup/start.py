#!/usr/bin/env python3

from socrate import supervisor

supervisor.start([
    {"name": "setup", "command": [
        "gunicorn", "-w", "4", "-b", ":80", "--access-logfile", "-",
        "--error-logfile", "-", "--preload", "main:app",
    ]},
])
