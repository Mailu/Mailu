# NOTE: only add qemu-arm-static if building for arm
ARG ARCH=""
ARG QEMU=other
FROM ${ARCH}php:8.0-apache as build_arm
ONBUILD COPY --from=balenalib/rpi-alpine:3.14 /usr/bin/qemu-arm-static /usr/bin/qemu-arm-static
FROM ${ARCH}php:8.0-apache as build_other


FROM build_${QEMU}
ARG VERSION
ENV TZ Etc/UTC

LABEL version=$VERSION

RUN set -eu \
 && apt update \
 && echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections \
 && apt install -y --no-install-recommends \
      python3 curl python3-pip git python3-multidict \
      python3-jinja2 gpg gpg-agent tzdata \
 && pip3 install socrate \
 && echo date.timezone=UTC > /usr/local/etc/php/conf.d/timezone.ini \
 && echo "ServerSignature Off\nServerName roundcube" >> /etc/apache2/apache2.conf \
 && sed -i 's,CustomLog.*combined$,\0 "'"expr=!(%{HTTP_USER_AGENT}=='health'\&\&(-R '127.0.0.1/8' || -R '::1'))"'",' /etc/apache2/sites-available/000-default.conf \
\
 && mark="$(apt-mark showmanual)" \
 && apt install -y --no-install-recommends \
      libfreetype6-dev libicu-dev libjpeg62-turbo-dev libldap2-dev libmagickwand-dev \
      libpng-dev libpq-dev libsqlite3-dev libzip-dev libpspell-dev libonig-dev \
 && ln -s php.ini-production /usr/local/etc/php/php.ini \
 && docker-php-ext-configure gd --with-jpeg --with-freetype \
 && docker-php-ext-install exif gd intl zip pspell pdo_mysql pdo_pgsql pdo_sqlite \
 && pecl install imagick \
 && docker-php-ext-enable imagick opcache \
 && apt-mark auto '.*' >/dev/null \
 && apt-mark manual ${mark} >/dev/null \
 && ldd "$(php -r 'echo ini_get("extension_dir");')"/*.so | awk '/=>/ { print $3 }' | sort -u | \
    xargs -r dpkg-query -S | cut -d: -f1 | sort -u | xargs -r apt-mark manual >/dev/null \
 && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
 && rm -rf /var/lib/apt/lists

ENV ROUNDCUBE_URL https://github.com/roundcube/roundcubemail/releases/download/1.5.1/roundcubemail-1.5.1-complete.tar.gz
ENV CARDDAV_URL https://github.com/mstilkerich/rcmcarddav/releases/download/v4.3.0/carddav-v4.3.0.tar.gz

RUN set -eu \
 && rm -rf /var/www/html/ \
 && cd /var/www \
 && curl -sL ${ROUNDCUBE_URL} | tar xz \
 && curl -sL ${CARDDAV_URL} | tar xz \
 && mv roundcubemail-* html \
 && mv carddav html/plugins/ \
 && cd html \
 && rm -rf CHANGELOG.md SECURITY.md INSTALL LICENSE README.md UPGRADING composer.json-dist installer composer.* \
 && ln -sf index.php /var/www/html/sso.php \
 && ln -sf /dev/stderr /var/www/html/logs/errors.log \
 && chown -R root:root . \
 && chown www-data:www-data logs temp \
 && chmod -R a+rX . \
 && a2enmod rewrite deflate expires headers \
 && echo date.timezone=${TZ} > /usr/local/etc/php/conf.d/timezone.ini \
 && rm -rf plugins/{autologon,example_addressbook,http_authentication,krb_authentication,new_user_identity,password,redundant_attachments,squirrelmail_usercopy,userinfo,virtuser_file,virtuser_query}

# enable database_attachments (and memcache?)

COPY mailu.php /var/www/html/plugins/mailu/mailu.php
COPY php.ini /
COPY config.inc.php /
COPY start.py /

EXPOSE 80/tcp
VOLUME /data
VOLUME /overrides

CMD /start.py

HEALTHCHECK CMD curl -f -L -H 'User-Agent: health' http://localhost/ || exit 1

RUN echo $VERSION >> /version
