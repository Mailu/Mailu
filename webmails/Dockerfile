# syntax=docker/dockerfile-upstream:1.4.3

FROM base

ARG VERSION
LABEL version=$VERSION

COPY snappymail/pubkey.asc /tmp/snappymail.asc
COPY roundcube/pubkey.asc /tmp/roundcube.asc
COPY roundcube/roundcube.diff /tmp/roundcube.diff

# php83-pecl-imagick php83-pecl-uuid are missing
RUN set -euxo pipefail \
  ; apk add --no-cache \
    nginx gpg gpg-agent patch \
    php83 php83-fpm php83-mbstring php83-zip php83-xml php83-simplexml php83-pecl-apcu \
    php83-dom php83-curl php83-exif gd php83-gd php83-iconv php83-intl php83-openssl php83-ctype \
    php83-pdo_sqlite php83-pdo_mysql php83-pdo_pgsql php83-pdo php83-sodium libsodium php83-tidy \
    php83-pspell php83-opcache php83-session php83-sockets php83-fileinfo php83-xmlreader php83-xmlwriter \
    aspell-uk aspell-ru aspell-fr aspell-de aspell-en \
  ; rm /etc/nginx/http.d/default.conf \
  ; rm /etc/php83/php-fpm.d/www.conf \
  ; ln -s /usr/bin/php83 /usr/bin/php \
  ; mkdir -m 700 /root/.gnupg/ \
  ; gpg --import /tmp/snappymail.asc \
  ; gpg --import /tmp/roundcube.asc \
  ; echo extension=snuffleupagus > /etc/php83/conf.d/snuffleupagus.ini \
  ; rm -f /tmp/roundcube.asc /tmp/snappymail.asc \
  ; mkdir -p /run/nginx /conf

# roundcube
ENV ROUNDCUBE_URL https://github.com/roundcube/roundcubemail/releases/download/1.6.6/roundcubemail-1.6.6-complete.tar.gz
ENV CARDDAV_URL https://github.com/mstilkerich/rcmcarddav/releases/download/v5.1.0/carddav-v5.1.0.tar.gz

RUN set -euxo pipefail \
  ; cd /var/www \
  ; curl -sLo /dev/shm/roundcube.tgz ${ROUNDCUBE_URL} \
  ; curl -sLo /dev/shm/roundcube.tgz.asc ${ROUNDCUBE_URL}.asc \
  ; gpg --status-fd 1 --verify /dev/shm/roundcube.tgz.asc /dev/shm/roundcube.tgz \
  ; tar xzf /dev/shm/roundcube.tgz \
  ; curl -sL ${CARDDAV_URL} | tar xz \
  ; mv roundcubemail-* roundcube \
  ; mkdir -p /var/www/roundcube/config \
  ; mv carddav roundcube/plugins/ \
  ; cd roundcube \
  ; rm -rf CHANGELOG.md SECURITY.md INSTALL LICENSE README.md UPGRADING composer.json-dist installer composer.* \
  ; ln -sf index.php /var/www/roundcube/public_html/sso.php \
  ; rm -rf plugins/{autologon,example_addressbook,http_authentication,krb_authentication,new_user_identity,password,redundant_attachments,squirrelmail_usercopy,userinfo,virtuser_file,virtuser_query} \
  ; patch -p0 < /tmp/roundcube.diff \
  ; rm /tmp/roundcube.diff

COPY roundcube/config/config.inc.php /conf/
COPY roundcube/login/ /var/www/roundcube/plugins/mailu/
COPY roundcube/config/config.inc.carddav.php /var/www/roundcube/plugins/carddav/config.inc.php

# snappymail

ENV SNAPPYMAIL_URL https://github.com/the-djmaze/snappymail/releases/download/v2.31.0/snappymail-2.31.0.tar.gz

RUN set -euxo pipefail \
  ; mkdir  /var/www/snappymail \
  ; cd /var/www/snappymail \
  ; curl -sLo /dev/shm/snappymail.tgz  ${SNAPPYMAIL_URL} \
  ; curl -sLo /dev/shm/snappymail.tgz.asc  ${SNAPPYMAIL_URL}.asc \
  ; gpg --status-fd 1 --verify /dev/shm/snappymail.tgz.asc /dev/shm/snappymail.tgz \
  ; cat /dev/shm/snappymail.tgz | tar xz

# SnappyMail login
COPY snappymail/login/include.php /var/www/snappymail/
COPY snappymail/login/sso.php /var/www/snappymail/

# Parsed and moved at startup
COPY snappymail/defaults/application.ini /defaults/
COPY snappymail/defaults/default.json /defaults/

# set perms
RUN set -euxo pipefail \
  ; chmod -R a+rX /var/www/snappymail \
  ; chown -R root:root /var/www/snappymail \
  ; chown -R mailu:mailu /var/www/snappymail/data \
  ; chown -R root:root /var/www/roundcube/ \
  ; chown -R mailu:mailu /var/www/roundcube/temp /var/www/roundcube/logs \
  ; chmod -R a+rX /var/www/roundcube

# common
COPY start.py /
COPY php.ini /defaults/
COPY php-webmail.conf /etc/php83/php-fpm.d/
COPY nginx-webmail.conf /conf/
COPY snuffleupagus.rules /etc/snuffleupagus.rules.tpl

# EXPOSE 80/tcp
VOLUME /data
VOLUME /overrides

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/ping || exit 1

RUN echo $VERSION >> /version
