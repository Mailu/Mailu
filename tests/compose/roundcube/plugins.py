#!/usr/bin/python3

import os
import re
import sys
import subprocess
import shutil
from socrate import conf
import logging as log


# Assign plugin env variables to local variables
REMOVE_RC_PLUGINS   = os.environ.get("REMOVE_RC_PLUGINS")
INSTALL_RC_PLUGINS  = os.environ.get("INSTALL_RC_PLUGINS")
ACTIVATE_RC_PLUGINS = os.environ.get("ACTIVATE_RC_PLUGINS", \
  re.sub('[^\s]+?/', '', INSTALL_RC_PLUGINS) \
  if INSTALL_RC_PLUGINS else None)
plugin_error        = False
# Check Composer
if shutil.which('composer') is not None:
  print("Composer Installed")
else:
  print("Composer Not Found. Installing..")
  os.system("curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/bin --filename=composer")

# Create composer.json if it does not exist
if os.path.isfile('composer.json'):
    print ("composer.json exists")
else:
    print ("Creating composer.json")
    os.system("cp composer.json-dist composer.json")

# Remove plugins from composer.json if REMOVE_RC_PLUGINS environment variable is set
if REMOVE_RC_PLUGINS:
  print(f'Removing plugins {REMOVE_RC_PLUGINS}')
  subprocess.check_call(['php', '-d', 'disable_functions=', '/usr/bin/composer', '--no-update', '--no-interaction', 'remove'] \
  + f'{REMOVE_RC_PLUGINS}'.split(),stderr=subprocess.STDOUT)


# Add plugins to composer.json if INSTALL_RC_PLUGINS environment variable is set
if INSTALL_RC_PLUGINS:
  print(f'Adding plugins {INSTALL_RC_PLUGINS}')
  subprocess.check_call(['php', '-d', 'disable_functions=', '/usr/bin/composer', '--prefer-dist', '--prefer-stable', '--no-update', \
  '--update-no-dev', '--no-interaction', '--optimize-autoloader', '--apcu-autoloader', 'require'] \
  + f"{INSTALL_RC_PLUGINS}".split() ,stderr=subprocess.STDOUT)


# Update plugins based on composer.json This installs and copies the plugins into the plugin directory
if INSTALL_RC_PLUGINS or REMOVE_RC_PLUGINS: 
  # Ensure composer.lock is updated
  try:
    print("Updating composer.lock")
    subprocess.check_call(['php', '-d', 'disable_functions=', '/usr/bin/composer', 'update', '--lock', '--prefer-dist', '--no-dev', '--no-interaction'],stderr=subprocess.STDOUT)
  except subprocess.CalledProcessError as e:
    print(e)
    print(f'composer.lock update failed. Please review your plugins list')
    plugin_error = True
  if not plugin_error:
    try:
      print('Installing/Updating roundcube plugins')
      result=subprocess.check_call(['php', '-d', 'disable_functions=', '/usr/bin/composer', '--prefer-dist', '--no-dev', '--no-interaction', \
      '--optimize-autoloader', '--apcu-autoloader', 'install'],stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
      print(e)
      print(f'roundcube plugins install failed')
      plugin_error = True

if ACTIVATE_RC_PLUGINS:
  print(f'Activating Roundcube plugins {ACTIVATE_RC_PLUGINS}')
  DEFAULT_RC_PLUGINS="archive zipdownload markasjunk managesieve enigma"
  RC_PLUGINS = f"{ACTIVATE_RC_PLUGINS}".split() + f"{DEFAULT_RC_PLUGINS}".split()
  # List of user defined plugins may be updated. We need to remove any existing entries and add them later.
  os.system("sed '/##\[USER/{:a;N;/END\]##/!ba};//d' config/config.inc.php > config/config.inc.php.temp")
  
  os.system("echo '##[USER_PLUGINS_START]##' >> config/config.inc.php.temp")
  
  os.system(f'echo "\$config[\'plugins\'] = {RC_PLUGINS};" >> config/config.inc.php.temp')
  
  os.system("echo '##[USER_PLUGINS_END]##' >> config/config.inc.php.temp")
  
  os.system("php -l config/config.inc.php.temp")
  try:
    print('Checking config is OK..')
    result=subprocess.check_call(['php', '-l', 'config/config.inc.php.temp'],stderr=subprocess.STDOUT)
    print(f'Config OK :-)')
    os.system("cp config/config.inc.php.temp config/config.inc.php")
  except subprocess.CalledProcessError as e:
    plugin_error = True
    print(f'Config error. Aborting activation..')
    print(f'Please check ACTIVATE_RC_PLUGINS env variable is in the format ACTIVATE_RC_PLUGINS=plugin1 plugin2')
else:
  # This is a convenient reset if ACTIVATE_RC_PLUGINS is not defined.
  # Roundcube will revert back to default plugins.
  # This also means the user has to explicitly state additional plugins in use.
  print(f'Resetting plugins to default')
  os.system("sed -i '/##\[USER/{:a;N;/END\]##/!ba};//d' config/config.inc.php")