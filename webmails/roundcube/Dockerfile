# syntax=docker/dockerfile-upstream:1.4.3

#roundcube image
FROM base

ARG VERSION
LABEL version=$VERSION

RUN apk add --no-cache \
    nginx gpg gpg-agent \
    php8 php8-fpm php8-mbstring php8-zip php8-xml php8-simplexml \
    php8-dom php8-curl php8-exif gd php8-gd php8-iconv php8-intl php8-openssl \
    php8-pdo_sqlite php8-pdo_mysql php8-pdo_pgsql php8-pdo php8-sodium libsodium php8-tidy php8-pecl-uuid \
    php8-pspell php8-pecl-imagick php8-opcache php8-session php8-sockets php8-fileinfo \
    && rm /etc/nginx/http.d/default.conf \
    && rm /etc/php8/php-fpm.d/www.conf \
    && mkdir -p /run/nginx \
    && mkdir -p /conf

ENV ROUNDCUBE_URL https://github.com/roundcube/roundcubemail/releases/download/1.5.3/roundcubemail-1.5.3-complete.tar.gz
ENV CARDDAV_URL https://github.com/mstilkerich/rcmcarddav/releases/download/v4.4.3/carddav-v4.4.3.tar.gz

RUN \
 cd /var/www \
 && curl -sL ${ROUNDCUBE_URL} | tar xz \
 && curl -sL ${CARDDAV_URL} | tar xz \
 && mv roundcubemail-* webmail \
 && mkdir -p /var/www/webmail/config \
 && mv carddav webmail/plugins/ \
 && cd webmail \
 && rm -rf CHANGELOG.md SECURITY.md INSTALL LICENSE README.md UPGRADING composer.json-dist installer composer.* \
 && ln -sf index.php /var/www/webmail/sso.php \
 && chmod -R u+w,a+rX /var/www/webmail \
 && chown -R nginx:nginx /var/www/webmail \
 && rm -rf plugins/{autologon,example_addressbook,http_authentication,krb_authentication,new_user_identity,password,redundant_attachments,squirrelmail_usercopy,userinfo,virtuser_file,virtuser_query}


# nginx / PHP config files
COPY config/nginx-roundcube.conf /conf/nginx-roundcube.conf
COPY config/php-roundcube.conf /etc/php8/php-fpm.d/roundcube.conf
COPY config/php.ini /conf/php.ini
COPY config/config.inc.php /conf/config.inc.php
COPY login/mailu.php /var/www/webmail/plugins/mailu/mailu.php
COPY config/config.inc.carddav.php /var/www/webmail/plugins/carddav/config.inc.php

COPY start.py /start.py

EXPOSE 80/tcp
VOLUME /data
VOLUME /overrides

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/ping || exit 1

RUN echo $VERSION >> /version
