#!/usr/bin/env python3

import os
import logging
import sys
import subprocess
import shutil
import hmac
import tempfile

from socrate import conf, system

env = os.environ

coerced = system.set_env(['ROUNDCUBE','SNUFFLEUPAGUS'])

# jinja context
context = {}
context.update(env)
context['ADMIN'] = coerced.get('ADMIN', False)

context["MAX_FILESIZE"] = str(int(int(env.get("MESSAGE_SIZE_LIMIT", "50000000")) * 0.66 / 1048576))

# Get the first DNS server
with open("/etc/resolv.conf") as handle:
    content = handle.read().split()
    resolver = content[content.index("nameserver") + 1]
    context["RESOLVER"] = f"[{resolver}]" if ":" in resolver else resolver

db_uri = env.get("SQLALCHEMY_DATABASE_URI_ROUNDCUBE", "sqlite:////data/roundcube.db")
db_flavor = env.get("ROUNDCUBE_DB_FLAVOR")
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
elif db_uri:
    context["DB_DSNW"] = db_uri
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
conf.jinja("/defaults/php.ini", context, "/etc/php84/php.ini")
snappymail_plugin = "/data/_data_/_default_/plugins/mailu-identities"
shutil.copytree(
    "/var/www/snappymail/mailu-plugins/mailu-identities",
    snappymail_plugin,
    dirs_exist_ok=True,
)

# setup permissions
os.system("chown -R mailu:mailu /data")
os.system(f"chown -R root:root {snappymail_plugin} && chmod -R a-w {snappymail_plugin}")

def demote(username='mailu'):
    def result():
        system.drop_privs_to(username)
    return result

def initialize_database(image_version_path="/version", marker_path="/data/.roundcube-version"):
    with open(image_version_path) as handle:
        version = handle.read().strip()
    try:
        with open(marker_path) as handle:
            previous_version = handle.read().strip()
    except FileNotFoundError:
        previous_version = None

    print("Initializing database")
    newly_initialized = False
    try:
        result = subprocess.check_output(["/var/www/roundcube/bin/initdb.sh", "--dir", "/var/www/roundcube/SQL"],
                                         stderr=subprocess.STDOUT, preexec_fn=demote())
        print(result.decode())
        newly_initialized = True
    except subprocess.CalledProcessError as exc:
        err = exc.stdout.decode()
        if "already exists" in err:
            print("Already initialized")
        else:
            print(err)
            raise SystemExit(3)

    if not newly_initialized and previous_version == version:
        print("Roundcube database is up to date for this image")
        return

    print("Upgrading database")
    try:
        subprocess.check_call(["/var/www/roundcube/bin/update.sh", "--version=?", "-y"], stderr=subprocess.STDOUT, preexec_fn=demote())
    except subprocess.CalledProcessError:
        raise SystemExit(4)
    print("Cleaning database")
    try:
        subprocess.check_call(["/var/www/roundcube/bin/cleandb.sh"], stderr=subprocess.STDOUT, preexec_fn=demote())
    except subprocess.CalledProcessError:
        raise SystemExit(5)

    # Never record a failed or interrupted upgrade as complete.
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=os.path.dirname(marker_path), delete=False) as handle:
            temporary_path = handle.name
            handle.write(version + "\n")
        os.replace(temporary_path, marker_path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


initialize_database()

# Configure nginx
conf.jinja("/conf/nginx-webmail.conf", context, "/etc/nginx/http.d/webmail.conf")
if os.path.exists("/var/run/nginx.pid"):
    os.system("nginx -s reload")

system.clean_env()

# run nginx
os.system("php-fpm84")
os.execv("/usr/sbin/nginx", ["nginx", "-g", "daemon off;"])

