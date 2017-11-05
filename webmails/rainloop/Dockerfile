FROM php:5-apache

RUN apt-get update && apt-get install -y \
      unzip

ENV RAINLOOP_URL https://github.com/RainLoop/rainloop-webmail/releases/download/v1.11.3/rainloop-community-1.11.3.zip

RUN rm -rf /var/www/html/ \
 && mkdir /var/www/html \
 && cd /var/www/html \
 && curl -L -O ${RAINLOOP_URL} \
 && unzip *.zip \
 && rm -f *.zip \
 && rm -rf data/ \
 && find . -type d -exec chmod 755 {} \; \
 && find . -type f -exec chmod 644 {} \; \
 && chown -R www-data: *

COPY include.php /var/www/html/include.php
COPY php.ini /usr/local/etc/php/conf.d/rainloop.ini

COPY config.ini /config.ini
COPY default.ini /default.ini

COPY start.sh /start.sh

CMD ["/start.sh"]
