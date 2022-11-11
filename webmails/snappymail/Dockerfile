# syntax=docker/dockerfile-upstream:1.4.3

#snappymail image
FROM base

ARG VERSION
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache \
    nginx curl \
    php81 php81-fpm php81-mbstring php81-zip php81-xml php81-simplexml \
    php81-dom php81-curl php81-exif gd php81-gd php81-iconv php81-intl php81-openssl \
    php81-pdo_sqlite php81-pdo php81-sodium libsodium php81-tidy php81-pecl-uuid \
  ; ln -s /usr/bin/php81 /usr/bin/php \
  ; rm /etc/nginx/http.d/default.conf \
  ; rm /etc/php81/php-fpm.d/www.conf \
  ; mkdir -p /run/nginx \
  ; mkdir -p /var/www/webmail \
  ; mkdir -p /config

# nginx / PHP config files
COPY config/nginx-snappymail.conf /config/
COPY config/php-snappymail.conf /etc/php81/php-fpm.d/snappymail.conf

# Parsed and moved at startup
COPY defaults/php.ini /defaults/
COPY defaults/application.ini /defaults/
COPY defaults/default.ini /defaults/

# Install Snappymail from source
ENV SNAPPYMAIL_URL https://github.com/the-djmaze/snappymail/releases/download/v2.19.4/snappymail-2.19.4.tar.gz
# Note. This is the last working snappymail version. 2.19.6 up to 2.20.6 do not work.

RUN set -euxo pipefail \
  ; cd /var/www/webmail \
  ; curl -sL  ${SNAPPYMAIL_URL} | tar xz \
  ; chmod -R u+w,a+rX /var/www/webmail \
  ; chown -R nginx:nginx /var/www/webmail

# SnappyMail login
COPY login/include.php /var/www/webmail/
COPY login/sso.php /var/www/webmail/

COPY start.py /
COPY config.py /

EXPOSE 80/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/ping || exit 1
RUN echo $VERSION >> /version
