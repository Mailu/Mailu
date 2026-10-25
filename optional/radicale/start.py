#!/usr/bin/env python3

import os

from socrate import supervisor

supervisor.clean_environment()
os.execvp("radicale", ["radicale", "-S", "-C", "/radicale.conf"])
