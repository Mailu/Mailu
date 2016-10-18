FROM php:5-apache

RUN apt-get update && apt-get install -y \
      libfreetype6-dev \
      libjpeg62-turbo-dev \
      libmcrypt-dev \
      libpng12-dev \
 && docker-php-ext-install pdo_mysql mcrypt

ENV ROUNDCUBE_URL https://github.com/roundcube/roundcubemail/releases/download/1.2.2/roundcubemail-1.2.2-complete.tar.gz

RUN echo date.timezone=UTC > /usr/local/etc/php/conf.d/timezone.ini

RUN cd /tmp \
 && curl -L -O ${ROUNDCUBE_URL} \
 && tar -xf *.tar.gz \
 && rm -f *.tar.gz \
 && rm -rf /var/www/html \
 && mv roundcubemail-* /var/www/html \
 && cd /var/www/html \
 && rm -rf CHANGELOG INSTALL LICENSE README.md UPGRADING composer.json-dist installer \
 && chown -R www-data: logs

COPY config.inc.php /var/www/html/config/

COPY start.sh /start.sh

CMD ["/start.sh"]
