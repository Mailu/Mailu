#!/usr/bin/python3

import os
import jinja2

convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

os.environ["MAX_FILESIZE"] = str(int(int(os.environ.get("MESSAGE_SIZE_LIMIT"))*0.66/1048576))

convert("/php.ini", "/usr/local/etc/php/conf.d/roundcube.ini")

# Fix some permissions
os.system("mkdir -p /data/gpg")
os.system("chown -R www-data:www-data /data")

# Run apache
os.execv("/usr/local/bin/apache2-foreground", ["apache2-foreground"])