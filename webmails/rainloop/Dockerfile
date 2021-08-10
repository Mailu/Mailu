ARG DISTRO=nginx:1.21-alpine
FROM $DISTRO

# Shared later between dovecot postfix nginx rspamd rainloop and roundloop
RUN apk add --no-cache \
    python3 py3-pip \
 && pip3 install socrate==0.2.0

# Shared layer between rainloop and roundcube
#  https://www.rainloop.net/docs/system-requirements/
#  Rainloop:
#     cURL            Builtin
#     iconv           php7-iconv
#     json            php7-json
#     libxml          php7-xml
#     dom             php7-dom
#     openssl         php7-openssl
#     DateTime        Builtin
#     PCRE            Builtin
#     SPL             Builtin
#  Recommended:
#     php7-fpm        FastCGI Process Manager
#  Optional PHP extension (for contacts):
#     php7-pdo        Accessing databases in PHP
#     php7-pdo_sqlite Access to SQLite 3 databases
RUN apk add --no-cache \
 && apk add php7 php7-fpm php7-curl php7-iconv php7-json php7-xml php7-dom php7-openssl \
 && rm /etc/nginx/conf.d/default.conf \
 && rm /etc/php7/php-fpm.d/www.conf

# nginx / PHP config files
COPY config/nginx-rainloop.conf /etc/nginx/conf.d/rainloop.conf
COPY config/php-rainloop.conf /etc/php7/php-fpm.d/rainloop.conf

# Rainloop login
COPY login/include.php /var/www/rainloop/include.php
COPY login/sso.php /var/www/rainloop/sso.php

# Parsed en moved at startup
COPY defaults/php.ini /defaults/php.ini
COPY defaults/application.ini /defaults/application.ini
COPY defaults/default.ini /defaults/default.ini

# Install Rainloop from source
ENV RAINLOOP_URL https://github.com/RainLoop/rainloop-webmail/releases/download/v1.16.0/rainloop-community-1.16.0.zip

RUN apk add --no-cache \
      unzip py3-jinja2 \
 && mkdir -p /var/www/rainloop \
 && cd /var/www/rainloop \
 && curl -L -O ${RAINLOOP_URL} \
 && unzip -q *.zip \
 && rm -f *.zip \
 && rm -rf data/ \
 && find . -type d -exec chmod 755 {} \; \
 && find . -type f -exec chmod 644 {} \; \
 && chown -R nginx:nginx /var/www/rainloop \
 && apk del unzip

COPY start.py /start.py

EXPOSE 80/tcp
VOLUME ["/data"]

CMD php-fpm7 && /start.py
