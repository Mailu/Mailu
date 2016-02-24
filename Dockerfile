

# Install the Webmail from source


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
