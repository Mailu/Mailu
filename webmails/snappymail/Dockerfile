# NOTE: only add file if building for arm
ARG ARCH=""
ARG QEMU=other
FROM ${ARCH}php:7.4-apache as build_arm
ONBUILD COPY --from=balenalib/rpi-alpine:3.10 /usr/bin/qemu-arm-static /usr/bin/qemu-arm-static

FROM ${ARCH}php:7.4-apache as build_other

FROM build_${QEMU}
#Shared layer between rainloop, roundcube and snappymail
RUN apt-get update && apt-get install -y \
  python3 curl python3-pip git python3-multidict \
  && rm -rf /var/lib/apt/lists \
  && echo "ServerSignature Off" >> /etc/apache2/apache2.conf

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube, snappymail
RUN pip3 install socrate

ENV SNAPPYMAIL_URL https://github.com/the-djmaze/snappymail/releases/download/v2.5.3/snappymail-2.5.3.tar.gz

RUN apt-get update && apt-get install -y \
      zlib1g-dev libzip4 libzip-dev libpq-dev \
      python3-jinja2 \
 && docker-php-ext-install zip pdo_mysql pdo_pgsql \
 && echo date.timezone=UTC > /usr/local/etc/php/conf.d/timezone.ini \
 && rm -rf /var/www/html/ \
 && mkdir /var/www/html \
 && cd /var/www/html \
 && curl -sL ${SNAPPYMAIL_URL} | tar xz \
 && rm -rf data/ \
 && find . -type d -exec chmod 755 {} \; \
 && find . -type f -exec chmod 644 {} \; \
 && chown -R www-data: * \
 && rm -rf /var/lib/apt/lists

COPY include.php /var/www/html/include.php
COPY php.ini /php.ini

COPY application.ini /application.ini
COPY default.ini /default.ini

COPY start.py /start.py

EXPOSE 80/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/ || exit 1
