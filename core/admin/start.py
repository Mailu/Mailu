#!/usr/bin/python3

import os
import logging as log
import sys

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO"))

os.system("flask mailu advertise")
os.system("flask db upgrade")

account = os.environ.get("INITIAL_ADMIN_ACCOUNT")
domain = os.environ.get("INITIAL_ADMIN_DOMAIN")
password = os.environ.get("INITIAL_ADMIN_PW")

if account is not None and domain is not None and password is not None:
    mode = os.environ.get("INITIAL_ADMIN_MODE", default="ifmissing")
    log.info("Creating initial admin accout %s@%s with mode %s",account,domain,mode)
    os.system("flask mailu admin %s %s '%s' --mode %s" % (account, domain, password, mode))

start_command="".join([
    "gunicorn -w 4 -b [::]:80 ",
    "--access-logfile - " if (log.root.level<=log.INFO) else "",
    "--error-logfile - ",
    "--preload ",
    "'mailu:create_app()'"])

os.system(start_command)
