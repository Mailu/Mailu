#!/usr/bin/python3

import os
import logging
import sys
from socrate import conf
import subprocess
import hmac

env = os.environ

logging.basicConfig(stream=sys.stderr, level=env.get("LOG_LEVEL", "WARNING"))

# jinja context
context = {}
context.update(env)

context["MAX_FILESIZE"] = str(int(int(env.get("MESSAGE_SIZE_LIMIT", "50000000")) * 0.66 / 1048576))

db_flavor = env.get("ROUNDCUBE_DB_FLAVOR", "sqlite")
if db_flavor == "sqlite":
    context["DB_DSNW"] = "sqlite:////data/roundcube.db"
elif db_flavor == "mysql":
    context["DB_DSNW"] = "mysql://%s:%s@%s/%s" % (
        env.get("ROUNDCUBE_DB_USER", "roundcube"),
        env.get("ROUNDCUBE_DB_PW"),
        env.get("ROUNDCUBE_DB_HOST", "database"),
        env.get("ROUNDCUBE_DB_NAME", "roundcube")
    )
elif db_flavor == "postgresql":
    context["DB_DSNW"] = "pgsql://%s:%s@%s/%s" % (
        env.get("ROUNDCUBE_DB_USER", "roundcube"),
        env.get("ROUNDCUBE_DB_PW"),
        env.get("ROUNDCUBE_DB_HOST", "database"),
        env.get("ROUNDCUBE_DB_NAME", "roundcube")
    )
else:
    print(f"Unknown ROUNDCUBE_DB_FLAVOR: {db_flavor}", file=sys.stderr)
    exit(1)

# derive roundcube secret key
secret_key = env.get("SECRET_KEY")
if not secret_key:
    try:
        secret_key = open(env.get("SECRET_KEY_FILE"), "r").read().strip()
    except Exception as exc:
        print(f"Can't read SECRET_KEY from file: {exc}", file=sys.stderr)
        exit(2)

context['SECRET_KEY'] = hmac.new(bytearray(secret_key, 'utf-8'), bytearray('ROUNDCUBE_KEY', 'utf-8'), 'sha256').hexdigest()

# roundcube plugins
# (using "dict" because it is ordered and "set" is not)
plugins = dict((p, None) for p in env.get("ROUNDCUBE_PLUGINS", "").replace(" ", "").split(",") if p and os.path.isdir(os.path.join("/var/www/plugins", p)))
if plugins:
    plugins["mailu"] = None
else:
    plugins = dict((k, None) for k in ["archive", "zipdownload", "markasjunk", "managesieve", "enigma", "carddav", "mailu"])

context["PLUGINS"] = ",".join(f"'{p}'" for p in plugins)

# create config files
conf.jinja("/php.ini", context, "/usr/local/etc/php/conf.d/roundcube.ini")
conf.jinja("/config.inc.php", context, "/var/www/html/config/config.inc.php")

# create dirs
os.system("mkdir -p /data/gpg")

print("Initializing database")
try:
    result = subprocess.check_output(["/var/www/html/bin/initdb.sh", "--dir", "/var/www/html/SQL"],
                                     stderr=subprocess.STDOUT)
    print(result.decode())
except subprocess.CalledProcessError as exc:
    err = exc.stdout.decode()
    if "already exists" in err:
        print("Already initialzed")
    else:
        print(err)
        exit(3)

print("Upgrading database")
try:
    subprocess.check_call(["/var/www/html/bin/update.sh", "--version=?", "-y"], stderr=subprocess.STDOUT)
except subprocess.CalledProcessError as exc:
    exit(4)
else:
    print("Cleaning database")
    try:
        subprocess.check_call(["/var/www/html/bin/cleandb.sh"], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        exit(5)

# setup permissions
os.system("chown -R www-data:www-data /data")

# clean env
[env.pop(key, None) for key in env.keys() if key == "SECRET_KEY" or key.startswith("ROUNDCUBE_")]

# run apache
os.execve("/usr/local/bin/apache2-foreground", ["apache2-foreground"], env)

