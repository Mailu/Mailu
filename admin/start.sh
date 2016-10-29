#!/bin/sh

python manage.py db upgrade
gunicorn -w 4 -b 0.0.0.0:80 --access-logfile - --error-logfile - mailu:app
