FROM php:7.0-apache

RUN apt-get update && apt-get install -y \
      libfreetype6-dev \
      libjpeg62-turbo-dev \
      libmcrypt-dev \
      libpng-dev \
 && docker-php-ext-install pdo_mysql mcrypt

ENV ROUNDCUBE_URL https://github.com/roundcube/roundcubemail/releases/download/1.3.3/roundcubemail-1.3.3-complete.tar.gz

RUN echo date.timezone=UTC > /usr/local/etc/php/conf.d/timezone.ini

RUN rm -rf /var/www/html/ \
 && cd /var/www \
 && curl -L -O ${ROUNDCUBE_URL} \
 && tar -xf *.tar.gz \
 && rm -f *.tar.gz \
 && mv roundcubemail-* html \
 && cd html \
 && rm -rf CHANGELOG INSTALL LICENSE README.md UPGRADING composer.json-dist installer \
 && chown -R www-data: logs \
 && sed -i 's/mod_php5.c/mod_php7.c/g' /var/www/html/.htaccess 

COPY config.inc.php /var/www/html/config/

COPY start.sh /start.sh

CMD ["/start.sh"]
