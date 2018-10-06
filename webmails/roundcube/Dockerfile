FROM php:7.2-apache

RUN apt-get update && apt-get install -y \
      zlib1g-dev \
 && docker-php-ext-install zip

ENV ROUNDCUBE_URL https://github.com/roundcube/roundcubemail/releases/download/1.3.7/roundcubemail-1.3.7-complete.tar.gz

RUN echo date.timezone=UTC > /usr/local/etc/php/conf.d/timezone.ini

RUN rm -rf /var/www/html/ \
 && cd /var/www \
 && curl -L -O ${ROUNDCUBE_URL} \
 && tar -xf *.tar.gz \
 && rm -f *.tar.gz \
 && mv roundcubemail-* html \
 && cd html \
 && rm -rf CHANGELOG INSTALL LICENSE README.md UPGRADING composer.json-dist installer \
 && sed -i 's,mod_php5.c,mod_php7.c,g' .htaccess \
 && chown -R www-data: logs temp

COPY php.ini /usr/local/etc/php/conf.d/roundcube.ini

COPY config.inc.php /var/www/html/config/

COPY start.sh /start.sh

EXPOSE 80/tcp
VOLUME ["/data"]

CMD ["/start.sh"]
