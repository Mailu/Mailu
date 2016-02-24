FROM php:apache

RUN apt-get update && apt-get install -y \
      libfreetype6-dev \
      libjpeg62-turbo-dev \
      libmcrypt-dev \
      libpng12-dev \
 && docker-php-ext-install pdo_mysql mcrypt

ENV ROUNDCUBE_URL https://downloads.sourceforge.net/project/roundcubemail/roundcubemail/1.1.4/roundcubemail-1.1.4-complete.tar.gz

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
