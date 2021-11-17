# NOTE: only add file if building for arm
ARG ARCH=""
ARG QEMU=other
FROM ${ARCH}php:7.4-apache as build_arm
ONBUILD COPY --from=balenalib/rpi-alpine:3.14 /usr/bin/qemu-arm-static /usr/bin/qemu-arm-static

FROM ${ARCH}php:7.4-apache as build_other

FROM build_${QEMU}
ARG VERSION
ENV TZ Etc/UTC

LABEL version=$VERSION
RUN echo $VERSION >> /version

#Shared layer between rainloop and roundcube
RUN apt-get update && apt-get install -y \
  python3 curl python3-pip git python3-multidict tzdata \
  && rm -rf /var/lib/apt/lists \
  && echo "ServerSignature Off\nServerName roundcube" >> /etc/apache2/apache2.conf \
  && sed -i 's,CustomLog.*combined$,\0 "'"expr=!(%{HTTP_USER_AGENT}=='health'\&\&(-R '127.0.0.1/8' || -R '::1'))"'",' /etc/apache2/sites-available/000-default.conf

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube
RUN pip3 install socrate

ENV ROUNDCUBE_URL https://github.com/roundcube/roundcubemail/releases/download/1.4.11/roundcubemail-1.4.11-complete.tar.gz

ENV CARDDAV_URL https://github.com/mstilkerich/rcmcarddav/releases/download/v4.1.2/carddav-v4.1.2.tar.gz

RUN apt-get update && apt-get install -y \
      zlib1g-dev libzip4 libzip-dev libpq-dev \
      python3-jinja2 \
      gpg \
 && docker-php-ext-install zip pdo_mysql pdo_pgsql \
 && rm -rf /var/www/html/ \
 && cd /var/www \
 && curl -sL ${ROUNDCUBE_URL} | tar xz \
 && curl -sL ${CARDDAV_URL} | tar xz \
 && mv roundcubemail-* html \
 && mv carddav html/plugins/ \
 && cd html \
 && rm -rf CHANGELOG INSTALL LICENSE README.md UPGRADING composer.json-dist installer composer.* \
 && sed -i 's,mod_php5.c,mod_php7.c,g' .htaccess \
 && sed -i 's,^php_value.*post_max_size,#&,g' .htaccess \
 && sed -i 's,^php_value.*upload_max_filesize,#&,g' .htaccess \
 && ln -sf index.php /var/www/html/sso.php \
 && ln -sf /dev/stderr /var/www/html/logs/errors.log \
 && chown -R root:root . \
 && chown www-data:www-data logs temp \
 && chmod -R a+rX . \
 && rm -rf /var/lib/apt/lists \
 && a2enmod rewrite deflate expires headers

COPY php.ini /php.ini
COPY config.inc.php /var/www/html/config/
COPY mailu.php /var/www/html/plugins/mailu/mailu.php
COPY start.py /start.py

EXPOSE 80/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK CMD curl -f -L -H 'User-Agent: health' http://localhost/ || exit 1
