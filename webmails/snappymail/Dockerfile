# syntax=docker/dockerfile-upstream:1.4.3

#snappymail image
FROM base

ARG VERSION
LABEL version=$VERSION

#  https://github.com/the-djmaze/snappymail/wiki/Installation-instructions#requirements
#  SnappyMail:
# SnappyMail requires PHP 7.4 (or a newer version) with the following extensions:
#
#     mbstring          php7-mbstring
#     Zlib              built-in OR php7-zip????
#     json              php7-json > php8-json is built-in php8 in alpine
#     libxml            php7-xml
#     dom               php7-dom

# Optional extensions:

#     cURL              php7-curl
#     exif              php7-exif
#     gd, gmagick or imagemagick gd and php7-gd
#     gnupg              gpgme and alpine has no php7-gnupg library :(
#     iconv             php7-iconv
#     intl              php7-intl
#     ldap              we don't use ldap
#     openssl           php7-openssl
#     PDO (MySQL/PostgreSQL/SQLite) (for contacts) php7-pdo_sqlite and php7-pdo
#     redis             NOT USED
#     Sodium            php7-sodium and libsodium
#     Tidy              php7-tidy
#     uuid (PECL)       php7-pecl-uuid
#     xxtea (PECL)      not found on alpine repo
#     zip               php7-zip
#php7-curl php7-iconv php7-json php7-xml php7-simplexml php7-dom php7-openssl php7-pdo php7-pdo_sqlite php7-mbstring \
RUN set -euxo pipefail \
  ; apk add --no-cache \
    nginx curl \
    php8 php8-fpm php8-mbstring php8-zip php8-xml php8-simplexml \
    php8-dom php8-curl php8-exif gd php8-gd php8-iconv php8-intl php8-openssl \
    php8-pdo_sqlite php8-pdo php8-sodium libsodium php8-tidy php8-pecl-uuid \
  ; rm /etc/nginx/http.d/default.conf \
  ; rm /etc/php8/php-fpm.d/www.conf \
  ; mkdir -p /run/nginx \
  ; mkdir -p /var/www/webmail \
  ; mkdir -p /config

# nginx / PHP config files
COPY config/nginx-snappymail.conf /config/nginx-snappymail.conf
COPY config/php-snappymail.conf /etc/php8/php-fpm.d/snappymail.conf

# Parsed and moved at startup
COPY defaults/php.ini /defaults/php.ini
COPY defaults/application.ini /defaults/application.ini
COPY defaults/default.ini /defaults/default.ini

# Install Snappymail from source
ENV SNAPPYMAIL_URL https://github.com/the-djmaze/snappymail/releases/download/v2.13.4/snappymail-2.13.4.tar.gz

RUN set -euxo pipefail \
  ; cd /var/www/webmail \
  ; curl -sL  ${SNAPPYMAIL_URL} | tar xz \
  ; chmod -R u+w,a+rX /var/www/webmail \
  ; chown -R nginx:nginx /var/www/webmail

# SnappyMail login
COPY login/include.php /var/www/webmail/include.php
COPY login/sso.php /var/www/webmail/sso.php

COPY start.py /
COPY config.py /config.py

EXPOSE 80/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/ping || exit 1
RUN echo $VERSION >> /version
