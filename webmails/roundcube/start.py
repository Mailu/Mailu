#!/usr/bin/python3

import os
import logging as log
import sys
from socrate import conf

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

max_filesize = str(int(int(os.environ.get("MESSAGE_SIZE_LIMIT"))*0.66/1048576))
os.environ["MAX_FILESIZE"] = max_filesize

conf.jinja("/php.ini", os.environ, "/usr/local/etc/php/conf.d/roundcube.ini")

# Replace default values in /var/www/html/.htaccess (upload_max_filesize=5M, post_max_size=6M)
os.system("sed -E -i 's/^php_value[[:space:]]+upload_max_filesize .*$/php_value   upload_max_filesize   %sM/g' /var/www/html/.htaccess" % (max_filesize))
os.system("sed -E -i 's/^php_value[[:space:]]+post_max_size .*$/php_value   post_max_size         %sM/g' /var/www/html/.htaccess" % (int(int(max_filesize)*1.05)))


# Fix some permissions
os.system("mkdir -p /data/gpg")
os.system("chown -R www-data:www-data /data")

# Run apache
os.execv("/usr/local/bin/apache2-foreground", ["apache2-foreground"])
