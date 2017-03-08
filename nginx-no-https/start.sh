#!/bin/sh

cp /etc/nginx/nginx.conf.default /etc/nginx/nginx.conf

nginx -g 'daemon off;'
