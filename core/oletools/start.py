#!/usr/bin/env python3

<<<<<<< HEAD
<<<<<<< HEAD
=======
import os
>>>>>>> 77c48294 (Hardened malloc was not disabled for oletools when an CPU with missing flags is used)
=======
>>>>>>> 9e1bf76a (Maybe fix olefy)
from socrate import system

system.set_env()

<<<<<<< HEAD
<<<<<<< HEAD
with open('/app/olefy.py') as olefy:
    exec(olefy.read())
=======
os.execl("/app/olefy.py", "olefy")
>>>>>>> 77c48294 (Hardened malloc was not disabled for oletools when an CPU with missing flags is used)
=======
with open('/app/olefy.py') as olefy:
    exec(olefy.read())
>>>>>>> 9e1bf76a (Maybe fix olefy)
