#!/usr/bin/env python3

<<<<<<< HEAD
=======
import os
>>>>>>> 77c48294 (Hardened malloc was not disabled for oletools when an CPU with missing flags is used)
from socrate import system

system.set_env()

<<<<<<< HEAD
with open('/app/olefy.py') as olefy:
    exec(olefy.read())
=======
os.execl("/app/olefy.py", "olefy")
>>>>>>> 77c48294 (Hardened malloc was not disabled for oletools when an CPU with missing flags is used)
