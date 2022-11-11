# syntax=docker/dockerfile-upstream:1.4.3

#roundcube image
FROM base

ARG VERSION
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache \
    nginx gpg gpg-agent \
    php81 php81-fpm php81-mbstring php81-zip php81-xml php81-simplexml \
    php81-dom php81-curl php81-exif gd php81-gd php81-iconv php81-intl php81-openssl \
    php81-pdo_sqlite php81-pdo_mysql php81-pdo_pgsql php81-pdo php81-sodium libsodium php81-tidy php81-pecl-uuid \
    php81-pspell php81-pecl-imagick php81-opcache php81-session php81-sockets php81-fileinfo \
  ; rm /etc/nginx/http.d/default.conf \
  ; rm /etc/php81/php-fpm.d/www.conf \
  ; ln -s /usr/bin/php81 /usr/bin/php \
  ; mkdir -p /run/nginx \
  ; mkdir -p /conf

ENV ROUNDCUBE_URL https://github.com/roundcube/roundcubemail/releases/download/1.5.3/roundcubemail-1.5.3-complete.tar.gz
ENV CARDDAV_URL https://github.com/mstilkerich/rcmcarddav/releases/download/v4.4.3/carddav-v4.4.3.tar.gz

RUN set -euxo pipefail \
  ; cd /var/www \
  ; curl -sL ${ROUNDCUBE_URL} | tar xz \
  ; curl -sL ${CARDDAV_URL} | tar xz \
  ; mv roundcubemail-* webmail \
  ; mkdir -p /var/www/webmail/config \
  ; mv carddav webmail/plugins/ \
  ; cd webmail \
  ; rm -rf CHANGELOG.md SECURITY.md INSTALL LICENSE README.md UPGRADING composer.json-dist installer composer.* \
  ; ln -sf index.php /var/www/webmail/sso.php \
  ; chmod -R u+w,a+rX /var/www/webmail \
  ; chown -R nginx:nginx /var/www/webmail \
  ; rm -rf plugins/{autologon,example_addressbook,http_authentication,krb_authentication,new_user_identity,password,redundant_attachments,squirrelmail_usercopy,userinfo,virtuser_file,virtuser_query}


# nginx / PHP config files
COPY config/nginx-roundcube.conf /conf/
COPY config/php-roundcube.conf /etc/php81/php-fpm.d/roundcube.conf
COPY config/php.ini /conf/
COPY config/config.inc.php /conf/
COPY login/mailu.php /var/www/webmail/plugins/mailu/
COPY config/config.inc.carddav.php /var/www/webmail/plugins/carddav/config.inc.php

COPY start.py /

EXPOSE 80/tcp
VOLUME /data
VOLUME /overrides

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/ping || exit 1

RUN echo $VERSION >> /version
