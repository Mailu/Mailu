ARG ARCH=""
ARG QEMU=other

# NOTE: only add file if building for arm
FROM ${ARCH}php:7.3-apache as build_arm
ONBUILD COPY --from=balenalib/rpi-alpine:3.10 /usr/bin/qemu-arm-static /usr/bin/qemu-arm-static

FROM ${ARCH}php:7.3-apache as build_other

FROM build_${QEMU}
#Shared layer between rainloop and roundcube
RUN apt-get update && apt-get install -y \
  python3 curl python3-pip git python3-multidict \
  && rm -rf /var/lib/apt/lists \
  && echo "ServerSignature Off" >> /etc/apache2/apache2.conf

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube
RUN pip3 install socrate

ENV RAINLOOP_URL https://github.com/RainLoop/rainloop-webmail/releases/download/v1.14.0/rainloop-community-1.14.0.zip

RUN apt-get update && apt-get install -y \
      unzip python3-jinja2 \
 && rm -rf /var/www/html/ \
 && mkdir /var/www/html \
 && cd /var/www/html \
 && curl -L -O ${RAINLOOP_URL} \
 && unzip -q *.zip \
 && rm -f *.zip \
 && rm -rf data/ \
 && find . -type d -exec chmod 755 {} \; \
 && find . -type f -exec chmod 644 {} \; \
 && chown -R www-data: * \
 && apt-get purge -y unzip \
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
