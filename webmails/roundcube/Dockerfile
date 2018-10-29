FROM php:7.2-apache

ENV ROUNDCUBE_URL https://github.com/roundcube/roundcubemail/releases/download/1.3.8/roundcubemail-1.3.8-complete.tar.gz

RUN apt-get update && apt-get install -y \
      zlib1g-dev curl \
 && docker-php-ext-install zip \
 && echo date.timezone=UTC > /usr/local/etc/php/conf.d/timezone.ini \
 && rm -rf /var/www/html/ \
 && cd /var/www \
 && curl -L -O ${ROUNDCUBE_URL} \
 && tar -xf *.tar.gz \
 && rm -f *.tar.gz \
 && mv roundcubemail-* html \
 && cd html \
 && rm -rf CHANGELOG INSTALL LICENSE README.md UPGRADING composer.json-dist installer \
 && sed -i 's,mod_php5.c,mod_php7.c,g' .htaccess \
 && chown -R www-data: logs temp \
 && rm -rf /var/lib/apt/lists

COPY php.ini /usr/local/etc/php/conf.d/roundcube.ini

COPY config.inc.php /var/www/html/config/

COPY start.sh /start.sh

EXPOSE 80/tcp
VOLUME ["/data"]

CMD ["/start.sh"]

HEALTHCHECK CMD curl -f -L http://localhost/ || exit 1
