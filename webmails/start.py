#!/usr/bin/env python3

import os
import logging
import sys
import subprocess
import shutil
import hmac

from socrate import conf, system

env = os.environ

logging.basicConfig(stream=sys.stderr, level=env.get("LOG_LEVEL", "WARNING"))

# jinja context
context = {}
context.update(env)

context["MAX_FILESIZE"] = str(int(int(env.get("MESSAGE_SIZE_LIMIT", "50000000")) * 0.66 / 1048576))
context["FRONT_ADDRESS"] = system.get_host_address_from_environment("FRONT", "front")
context["IMAP_ADDRESS"] = system.get_host_address_from_environment("IMAP", "imap")

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

context['ROUNDCUBE_KEY'] = hmac.new(bytearray(secret_key, 'utf-8'), bytearray('ROUNDCUBE_KEY', 'utf-8'), 'sha256').hexdigest()
context['SNUFFLEPAGUS_KEY'] = hmac.new(bytearray(secret_key, 'utf-8'), bytearray('SNUFFLEPAGUS_KEY', 'utf-8'), 'sha256').hexdigest()
conf.jinja("/etc/snuffleupagus.rules.tpl", context, "/etc/snuffleupagus.rules")

# roundcube plugins
# (using "dict" because it is ordered and "set" is not)
plugins = dict((p, None) for p in env.get("ROUNDCUBE_PLUGINS", "").replace(" ", "").split(",") if p and os.path.isdir(os.path.join("/var/www/roundcube/plugins", p)))
if plugins:
    plugins["mailu"] = None
else:
    plugins = dict((k, None) for k in ["archive", "zipdownload", "markasjunk", "managesieve", "enigma", "carddav", "mailu"])

context["PLUGINS"] = ",".join(f"'{p}'" for p in plugins)

# add overrides
context["INCLUDES"] = sorted(inc for inc in os.listdir("/overrides") if inc.endswith((".inc", ".inc.php"))) if os.path.isdir("/overrides") else []

# calculate variables for config file
context["SESSION_TIMEOUT_MINUTES"] = max(int(env.get("SESSION_TIMEOUT", "3600")) // 60, 1)

# create config files
conf.jinja("/conf/config.inc.php", context, "/var/www/roundcube/config/config.inc.php")

# create dirs
os.system("mkdir -p /data/gpg")

print("Initializing database")
try:
    result = subprocess.check_output(["/var/www/roundcube/bin/initdb.sh", "--dir", "/var/www/roundcube/SQL"],
                                     stderr=subprocess.STDOUT)
    print(result.decode())
except subprocess.CalledProcessError as exc:
    err = exc.stdout.decode()
    if "already exists" in err:
        print("Already initialized")
    else:
        print(err)
        exit(3)

print("Upgrading database")
try:
    subprocess.check_call(["/var/www/roundcube/bin/update.sh", "--version=?", "-y"], stderr=subprocess.STDOUT)
except subprocess.CalledProcessError as exc:
    exit(4)
else:
    print("Cleaning database")
    try:
        subprocess.check_call(["/var/www/roundcube/bin/cleandb.sh"], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        exit(5)

base = "/data/_data_/_default_/"
shutil.rmtree(base + "domains/", ignore_errors=True)
os.makedirs(base + "domains", exist_ok=True)
os.makedirs(base + "configs", exist_ok=True)

conf.jinja("/defaults/default.json", context, "/data/_data_/_default_/domains/default.json")
conf.jinja("/defaults/application.ini", context, "/data/_data_/_default_/configs/application.ini")
conf.jinja("/defaults/php.ini", context, "/etc/php81/php.ini")

# setup permissions
os.system("chown -R mailu:mailu /data")

# Configure nginx
conf.jinja("/conf/nginx-webmail.conf", context, "/etc/nginx/http.d/webmail.conf")
if os.path.exists("/var/run/nginx.pid"):
    os.system("nginx -s reload")

# clean env
[env.pop(key, None) for key in env.keys() if key == "SECRET_KEY" or key.endswith("_KEY")]

# run nginx
os.system("php-fpm81")
os.execv("/usr/sbin/nginx", ["nginx", "-g", "daemon off;"])

