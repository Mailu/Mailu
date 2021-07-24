FROM php:8-fpm-alpine

# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip git bash \
  && pip3 install --upgrade pip

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube
RUN pip3 install socrate

ENV RAINLOOP_URL https://github.com/RainLoop/rainloop-webmail/releases/download/v1.16.0/rainloop-community-1.16.0.zip

RUN rm -rf /var/www/webmail \
 && mkdir -p /var/www/webmail/ \
 && cd /var/www/webmail \
 && curl -L -O ${RAINLOOP_URL} \
 && unzip -q *.zip \
 && rm -f *.zip \
 && rm -rf data/

COPY include.php /var/www/webmail/include.php
COPY sso.php /var/www/webmail/sso.php
COPY php.ini /php.ini

RUN chmod a+rX -R /var/www \
 && chown -R www-data:www-data /var/www

COPY application.ini /application.ini
COPY default.ini /default.ini

COPY start.py /start.py

EXPOSE 9000/tcp
VOLUME ["/data"]

CMD /start.py

#HEALTHCHECK CMD curl -f -L http://localhost/ || exit 1
