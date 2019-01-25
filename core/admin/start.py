#!/usr/bin/python3

import os

os.system("flask mailu advertise")
os.system("flask db upgrade")

if 'INITIAL_ADMIN_ACCOUNT' in os.environ and 'INITIAL_ADMIN_DOMAIN' in os.environ and 'INITIAL_ADMIN_PW'  in os.environ:
    mode = 'ifmissing'
    if 'INITIAL_ADMIN_MODE' in os.environ:
        mode = os.environ['INITIAL_ADMIN_MODE']
    os.system("flask mailu admin %s %s '%s' --mode %s" % (
        os.environ['INITIAL_ADMIN_ACCOUNT'], os.environ['INITIAL_ADMIN_DOMAIN'], os.environ['INITIAL_ADMIN_PW'], mode))

os.system("gunicorn -w 4 -b :80 --access-logfile - --error-logfile - --preload 'mailu:create_app()'")
