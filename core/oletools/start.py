#!/usr/bin/env python3

import os
from socrate import system

system.set_env()

os.execl("/app/olefy.py", "olefy")