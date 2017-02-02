#!/bin/sh

if [[ ! -z ENABLE_CERTBOT && ! -f /certs/cert.pem ]]; then
  cp /etc/nginx/nginx.conf.fallback /etc/nginx/nginx.conf
fi

nginx -g 'daemon off;'
