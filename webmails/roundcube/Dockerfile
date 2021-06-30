# NOTE: only add file if building for arm
ARG ARCH=""
ARG QEMU=other
FROM ${ARCH}php:7.4-apache as build_arm
ONBUILD COPY --from=balenalib/rpi-alpine:3.10 /usr/bin/qemu-arm-static /usr/bin/qemu-arm-static

FROM ${ARCH}php:7.4-apache as build_other

FROM build_${QEMU}
#Shared layer between rainloop and roundcube
RUN apt-get update && apt-get install -y \
  python3 curl python3-pip git python3-multidict \
  && rm -rf /var/lib/apt/lists \
  && echo "ServerSignature Off" >> /etc/apache2/apache2.conf

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube
RUN pip3 install socrate

ENV ROUNDCUBE_URL https://github.com/roundcube/roundcubemail/releases/download/1.4.11/roundcubemail-1.4.11-complete.tar.gz

ENV CARDDAV_URL https://github.com/mstilkerich/rcmcarddav/releases/download/v4.1.2/carddav-v4.1.2.tar.gz

RUN apt-get update && apt-get install -y \
      zlib1g-dev libzip4 libzip-dev libpq-dev \
      python3-jinja2 \
      gpg \
 && docker-php-ext-install zip pdo_mysql pdo_pgsql \
 && echo date.timezone=UTC > /usr/local/etc/php/conf.d/timezone.ini \
 && rm -rf /var/www/html/ \
 && cd /var/www \
 && curl -sL ${ROUNDCUBE_URL} | tar xz \
 && curl -sL ${CARDDAV_URL} | tar xz \
 && mv roundcubemail-* html \
 && mv carddav html/plugins/ \
 && cd html \
 && rm -rf CHANGELOG INSTALL LICENSE README.md UPGRADING composer.json-dist installer \
 && sed -i 's,mod_php5.c,mod_php7.c,g' .htaccess \
 && sed -i 's,^php_value.*post_max_size,#&,g' .htaccess \
 && sed -i 's,^php_value.*upload_max_filesize,#&,g' .htaccess \
 && chown -R www-data: logs temp \
 && rm -rf /var/lib/apt/lists

COPY php.ini /php.ini
COPY config.inc.php /var/www/html/config/
COPY mailu.php /var/www/html/plugins/mailu/mailu.php
COPY start.py /start.py

EXPOSE 80/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/ || exit 1
