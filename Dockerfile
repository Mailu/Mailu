FROM python:3

# Install required system packages
RUN export DEBIAN_FRONTEND=noninteractive \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      postfix dovecot-imapd dovecot-sqlite dovecot-lmtpd \
      dovecot-sieve dovecot-managesieved \
      dovecot-antispam spamassassin spamc clamav \
      php5-fpm php5-mysql php5-imap php5-sqlite php5-mcrypt \
      supervisor rsyslog nginx sqlite3 \
 && apt-get clean

# Install the Webmail from source
ENV ROUNDCUBE_VERSION 1.1.4-complete
RUN curl -L -O https://downloads.sourceforge.net/project/roundcubemail/roundcubemail/1.1.4/roundcubemail-${ROUNDCUBE_VERSION}.tar.gz \
 && tar -xf roundcubemail-${ROUNDCUBE_VERSION}.tar.gz \
 && rm -f roundcubemail-${ROUNDCUBE_VERSION}.tar.gz \
 && mv roundcubemail-* /webmail

# Install the Web admin panel
COPY admin /admin
RUN pip install -r /admin/requirements.txt

# Configure the webmail
RUN cd /webmail \
 && rm -rf CHANGELOG INSTALL LICENSE README.md UPDGRADING composer.json-dist temp logs \
 && ln -s /data/logs/webmail logs \
 && ln -s /data/webmail/temp temp \
 && ln -s /etc/roundcube.inc.php config/config.inc.php

# Load the configuration
COPY config /etc/

# Copy the entrypoint
COPY start.sh /start.sh

# Explicitely specify the configuration file to avoid problems when
# the default configuration path changes.
CMD "/start.sh"
