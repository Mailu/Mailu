#!/usr/bin/env python3

import os
import logging
import sys
import subprocess
import hmac

from socrate import conf

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
plugins = dict((p, None) for p in env.get("ROUNDCUBE_PLUGINS", "").replace(" ", "").split(",") if p and os.path.isdir(os.path.join("/var/www/webmail/plugins", p)))
if plugins:
    plugins["mailu"] = None
else:
    plugins = dict((k, None) for k in ["archive", "zipdownload", "markasjunk", "managesieve", "enigma", "carddav", "mailu"])

context["PLUGINS"] = ",".join(f"'{p}'" for p in plugins)

# add overrides
context["INCLUDES"] = sorted(inc for inc in os.listdir("/overrides") if inc.endswith(".inc")) if os.path.isdir("/overrides") else []

# calculate variables for config file
context["SESSION_TIMEOUT_MINUTES"] = max(int(env.get("SESSION_TIMEOUT", "3600")) // 60, 1)

# create config files
conf.jinja("/conf/php.ini", context, "/etc/php8/php.ini")
conf.jinja("/conf/config.inc.php", context, "/var/www/webmail/config/config.inc.php")

# create dirs
os.system("mkdir -p /data/gpg")

print("Initializing database")
try:
    result = subprocess.check_output(["/var/www/webmail/bin/initdb.sh", "--dir", "/var/www/webmail/SQL"],
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
    subprocess.check_call(["/var/www/webmail/bin/update.sh", "--version=?", "-y"], stderr=subprocess.STDOUT)
except subprocess.CalledProcessError as exc:
    exit(4)
else:
    print("Cleaning database")
    try:
        subprocess.check_call(["/var/www/webmail/bin/cleandb.sh"], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        exit(5)

# setup permissions
os.system("chown -R nginx:nginx /data")
os.system("chmod -R a+rX /var/www/webmail/")

# Configure nginx
conf.jinja("/conf/nginx-roundcube.conf", context, "/etc/nginx/http.d/roundcube.conf")
if os.path.exists("/var/run/nginx.pid"):
    os.system("nginx -s reload")

# clean env
[env.pop(key, None) for key in env.keys() if key == "SECRET_KEY" or key.startswith("ROUNDCUBE_")]

# run nginx
os.system("php-fpm8")
os.execv("/usr/sbin/nginx", ["nginx", "-g", "daemon off;"])

