#!/usr/bin/python3

import os

# Fix some permissions
os.system("mkdir -p /data/gpg")
os.system("chown -R www-data:www-data /data")

# Run apache
os.execv("/usr/local/bin/apache2-foreground", ["apache2-foreground"])