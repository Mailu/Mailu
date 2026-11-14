#!/usr/bin/env python3

from socrate import system, supervisor

system.set_env()
supervisor.start([
    {"name": "olefy", "command": ["python3", "/run_olefy.py"]},
])
