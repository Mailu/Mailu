#!/bin/bash

#Switch to roundcube directory 
cd /var/www/html

# Skip installation if not required
if [[ ! -z "${INSTALL_RC_PLUGINS}" ]] || [[ ! -z "${REMOVE_RC_PLUGINS}" ]]; then
  # Check if composer is installed and install if missing
  if [[ ! -x "$(command -v composer)" ]]; then
    echo "Composer not found. Installing.."
    curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/bin --filename=composer
  else
    echo "Composer Installed."
  fi
fi

# Create composer.json if it does not exist
if [[ ! -f composer.json  ]]; then
  echo "Creating composer.json"
  cp composer.json-dist composer.json
else
  echo "File composer.json exists."
fi

# Remove plugins from composer.json if REMOVE_RC_PLUGINS environment variable is set
if [[ ! -z "${REMOVE_RC_PLUGINS}" ]]; then
  echo "Removing plugins ${REMOVE_RC_PLUGINS}"
  php -d "disable_functions=" /usr/bin/composer --no-update --no-interaction remove \
  ${REMOVE_RC_PLUGINS}
fi

# Add plugins to composer.json if INSTALL_RC_PLUGINS environment variable is set
if [[ ! -z "${INSTALL_RC_PLUGINS}" ]]; then
  echo "Adding plugins ${INSTALL_RC_PLUGINS}"
  php -d "disable_functions=" /usr/bin/composer --prefer-dist --prefer-stable --no-update --update-no-dev \
  --no-interaction --optimize-autoloader --apcu-autoloader require \
  ${INSTALL_RC_PLUGINS}
fi


# Update plugins based on composer.json This installs/copies the plugins into the plugin directory
if [[ ! -z "${INSTALL_RC_PLUGINS}" ]] || [[ ! -z "${REMOVE_RC_PLUGINS}" ]]; then
  echo "Installing/Updating roundcube plugins"
  php -d "disable_functions=" /usr/bin/composer --prefer-dist --no-dev \
  --no-interaction --optimize-autoloader --apcu-autoloader install
fi

# Activate plugins
# This is most sensitive and should be done with care so as not to break the config script.
# We should check this config is valid before we proceed.
if [[ ! -z "${ACTIVATE_RC_PLUGINS}" ]]; then

  # Define default plugins shipped with this Roundcube Installation
  DEFAULT_RC_PLUGINS="archive zipdownload markasjunk managesieve enigma"
  DEFAULT_RC_PLUGINS_LIST="'${DEFAULT_RC_PLUGINS//[[:space:]]/', '}'"
  
  echo "Activating Roundcube plugins ${ACTIVATE_RC_PLUGINS}"
  
  # Convert ACTIVATE_RC_PLUGINS to comma separated list
  RC_PLUGINS_LIST="'${ACTIVATE_RC_PLUGINS//[[:space:]]/', '}'"
  
  
  sed "s/\$config\['plugins'\].*;/\$config['plugins'] = array(${RC_PLUGINS_LIST}, ${DEFAULT_RC_PLUGINS_LIST});/" config/config.inc.php > config/updated.config.inc.php
  # Abort activation of new plugins if updated config has an error
  if php -l config/updated.config.inc.php; then
    echo "Config OK :-)"
    \cp config/updated.config.inc.php config/config.inc.php
  else
    echo "Config error. Aborting activation.."
    echo "Please check ACTIVATE_RC_PLUGINS env variable is in the format ACTIVATE_RC_PLUGINS=plugin1 plugin2"
  fi
  
else
  # This is a convenient reset if ACTIVATE_RC_PLUGINS is not defined.
  # Roundcube will revert back to default plugins.
  # This also means the user has to explicitly state additional plugins in use.
  sed -i "s/\$config\['plugins'\].*;/\$config['plugins'] = array($DEFAULT_RC_PLUGINS_LIST);/" config/config.inc.php
fi

# Proceed with command defined in CMD
exec "$@"