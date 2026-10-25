#!/usr/bin/env python3

import os

from socrate import supervisor

supervisor.clean_environment()
os.execvp("gunicorn", [
    "gunicorn", "-w", "4", "-b", ":80", "--access-logfile", "-",
    "--error-logfile", "-", "--preload", "main:app",
])
