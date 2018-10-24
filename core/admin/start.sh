#!/bin/sh

python manage.py advertise
python manage.py db upgrade
gunicorn -w 4 -b :80 --access-logfile - --error-logfile - --preload mailu:app
