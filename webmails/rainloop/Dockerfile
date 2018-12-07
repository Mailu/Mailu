FROM php:7.2-apache
#Shared layer between rainloop and roundcube
RUN apt-get update && apt-get install -y \
  python3 curl \
  && rm -rf /var/lib/apt/lists

ENV RAINLOOP_URL https://github.com/RainLoop/rainloop-webmail/releases/download/v1.12.1/rainloop-community-1.12.1.zip

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

COPY config.ini /config.ini
COPY default.ini /default.ini

COPY start.py /start.py

EXPOSE 80/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/ || exit 1
