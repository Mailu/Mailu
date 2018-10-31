#!/usr/bin/python3

import os

os.system("python3 manage.py advertise")
os.system("python3 manage.py db upgrade")
os.system("gunicorn -w 4 -b :80 --access-logfile - --error-logfile - --preload mailu:app")
