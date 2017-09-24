#!/bin/sh

jinja2 /conf/nginx.conf > /etc/nginx/nginx.conf

exec nginx -g 'daemon off;'
