#!/bin/sh

if [ -z $ENABLE_CERTBOT ] || [ -f /certs/cert.pem ]
then
  cp /etc/nginx/nginx.conf.default /etc/nginx/nginx.conf
else
  openssl req -newkey rsa:2048 -x509 -keyout /tmp/snakeoil.pem -out /tmp/snakeoil.pem -days 365 -nodes -subj "/C=NA/ST=None/L=None/O=None/CN=$DOMAIN"
  cp /etc/nginx/nginx.conf.fallback /etc/nginx/nginx.conf
fi

if [ ! -r /etc/nginx/dhparam.pem ]; then
  openssl dhparam -out /etc/nginx/dhparam.pem $NGINX_SSL_DHPARAM_BITS
fi

nginx -g 'daemon off;'
