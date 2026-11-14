#!/usr/bin/env python3

import subprocess

from socrate import supervisor

# Existing volumes were written by root. Repair ownership before starting the
# service as mailu, including Radicale's locks and caches.
subprocess.run(["chown", "-hR", "mailu:mailu", "/data"], check=True)

supervisor.start([
    {"name": "radicale", "user": "mailu", "command": ["python3", "/run_radicale.py"]},
])
