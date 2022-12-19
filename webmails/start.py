#!/usr/bin/env python3

import os
import logging
from pwd import getpwnam
import sys
import subprocess
import shutil
import hmac

from socrate import conf, system

env = os.environ

logging.basicConfig(stream=sys.stderr, level=env.get("LOG_LEVEL", "WARNING"))
system.set_env(['ROUNDCUBE','SNUFFLEUPAGUS'])

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

base = "/data/_data_/_default_/"
shutil.rmtree(base + "domains/", ignore_errors=True)
os.makedirs(base + "domains", exist_ok=True)
os.makedirs(base + "configs", exist_ok=True)

conf.jinja("/defaults/default.json", context, "/data/_data_/_default_/domains/default.json")
conf.jinja("/defaults/application.ini", context, "/data/_data_/_default_/configs/application.ini")
conf.jinja("/defaults/php.ini", context, "/etc/php81/php.ini")

# setup permissions
os.system("chown -R mailu:mailu /data")

def demote(user_uid, user_gid):
    def result():
        os.setgid(user_gid)
        os.setuid(user_uid)
    return result
id_mailu = getpwnam('mailu')

print("Initializing database")
try:
    result = subprocess.check_output(["/var/www/roundcube/bin/initdb.sh", "--dir", "/var/www/roundcube/SQL"],
                                     stderr=subprocess.STDOUT, preexec_fn=demote(id_mailu.pw_uid,id_mailu.pw_gid))
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
    subprocess.check_call(["/var/www/roundcube/bin/update.sh", "--version=?", "-y"], stderr=subprocess.STDOUT, preexec_fn=demote(id_mailu.pw_uid,id_mailu.pw_gid))
except subprocess.CalledProcessError as exc:
    exit(4)
else:
    print("Cleaning database")
    try:
        subprocess.check_call(["/var/www/roundcube/bin/cleandb.sh"], stderr=subprocess.STDOUT, preexec_fn=demote(id_mailu.pw_uid,id_mailu.pw_gid))
    except subprocess.CalledProcessError as exc:
        exit(5)

# Configure nginx
conf.jinja("/conf/nginx-webmail.conf", context, "/etc/nginx/http.d/webmail.conf")
if os.path.exists("/var/run/nginx.pid"):
    os.system("nginx -s reload")

system.clean_env()

# run nginx
os.system("php-fpm81")
os.execv("/usr/sbin/nginx", ["nginx", "-g", "daemon off;"])

