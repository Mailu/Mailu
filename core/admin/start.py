#!/usr/local/bin/python3

import os

os.system("python manage.py advertise")
os.system("python manage.py db upgrade")
os.system("gunicorn -w 4 -b :80 --access-logfile - --error-logfile - --preload mailu:app")