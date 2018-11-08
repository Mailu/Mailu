#!/bin/sh

flask mailu advertise
flask db upgrade

gunicorn -w 4 -b :80 --access-logfile - --error-logfile - --preload "$FLASK_APP:create_app()"
