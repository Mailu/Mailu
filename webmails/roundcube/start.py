#!/usr/bin/python3

import os
import logging as log
import sys
from socrate import conf
import subprocess

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

os.environ["MAX_FILESIZE"] = str(int(int(os.environ.get("MESSAGE_SIZE_LIMIT"))*0.66/1048576))

db_flavor=os.environ.get("ROUNDCUBE_DB_FLAVOR","sqlite")
if db_flavor=="sqlite":
    os.environ["DB_DSNW"]="sqlite:////data/roundcube.db"
elif db_flavor=="mysql":
    os.environ["DB_DSNW"]="mysql://%s:%s@%s/%s" % (
        os.environ.get("ROUNDCUBE_DB_USER","roundcube"),
        os.environ.get("ROUNDCUBE_DB_PW"),
        os.environ.get("ROUNDCUBE_DB_HOST","database"),
        os.environ.get("ROUNDCUBE_DB_NAME","roundcube")
        )
elif db_flavor=="postgresql":
    os.environ["DB_DSNW"]="pgsql://%s:%s@%s/%s" % (
        os.environ.get("ROUNDCUBE_DB_USER","roundcube"),
        os.environ.get("ROUNDCUBE_DB_PW"),
        os.environ.get("ROUNDCUBE_DB_HOST","database"),
        os.environ.get("ROUNDCUBE_DB_NAME","roundcube")
        )
else:
    print("Unknown ROUNDCUBE_DB_FLAVOR: %s",db_flavor)
    exit(1)



conf.jinja("/php.ini", os.environ, "/usr/local/etc/php/conf.d/roundcube.ini")

# Fix some permissions
os.system("mkdir -p /data/gpg /var/www/html/logs")
os.system("touch /var/www/html/logs/errors")
os.system("chown -R www-data:www-data /data /var/www/html/logs")

try:
    print("Initializing database")
    result=subprocess.check_output(["/var/www/html/bin/initdb.sh","--dir","/var/www/html/SQL"],stderr=subprocess.STDOUT)
    print(result.decode())
except subprocess.CalledProcessError as e:
    if "already exists" in e.stdout.decode():
        print("Already initialzed")
    else:
        print(e.stdout.decode())
        quit(1)

try:
    print("Upgrading database")
    subprocess.check_call(["/var/www/html/bin/update.sh","--version=?","-y"],stderr=subprocess.STDOUT)
except subprocess.CalledProcessError as e:
    quit(1)

# Tail roundcube logs
subprocess.Popen(["tail","-f","-n","0","/var/www/html/logs/errors"])

# Run apache
os.execv("/usr/local/bin/apache2-foreground", ["apache2-foreground"])
