#!/usr/bin/env python3

import os
import sys

from socrate import system, supervisor

system.set_env()
supervisor.clean_environment()
os.execv(sys.executable, [sys.executable, "/run_olefy.py"])
