#!/usr/bin/python3

import os

os.system("flask mailu advertise")
os.system("flask db upgrade")

account = os.environ.get("INITIAL_ADMIN_ACCOUNT")
domain = os.environ.get("INITIAL_ADMIN_DOMAIN")
password = os.environ.get("INITIAL_ADMIN_PW")

if account is not None and domain is not None and password is not None:
    mode = os.environ.get("INITIAL_ADMIN_MODE", default="ifmissing")
    os.system("flask mailu admin %s %s '%s' --mode %s" % (account, domain, password, mode))

os.system("gunicorn -w 4 -b :80 --access-logfile - --error-logfile - --preload 'mailu:create_app()'")
