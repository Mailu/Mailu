#!/usr/bin/python3

import os

os.system("flask mailu advertise")
os.system("flask db upgrade")
os.system("gunicorn -w 4 -b :80 --access-logfile - --error-logfile - --preload 'mailu:create_app()'")
