FROM php:7.3-apache
#Shared layer between rainloop and roundcube
RUN apt-get update && apt-get install -y \
  python3 curl python3-pip git \
  && rm -rf /var/lib/apt/lists \
  && echo "ServerSignature Off" >> /etc/apache2/apache2.conf

ENV ROUNDCUBE_URL https://github.com/roundcube/roundcubemail/releases/download/1.3.9/roundcubemail-1.3.9-complete.tar.gz

RUN apt-get update && apt-get install -y \
      zlib1g-dev libzip4 libzip-dev \
      python3-jinja2 \
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

# Shared layer between rspamd, postfix, dovecot, unbound, rainloop, roundcube and nginx
RUN pip3 install git+https://github.com/Mailu/MailuStart.git#egg=mailustart

COPY php.ini /php.ini
COPY config.inc.php /var/www/html/config/
COPY start.py /start.py

EXPOSE 80/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/ || exit 1
