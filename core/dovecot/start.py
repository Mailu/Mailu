#!/usr/bin/python

import jinja2
import os
import socket
import glob

if "DB_TYPE" in os.environ and os.environ["DB_TYPE"] == "mysql":
	if "DB_HOST" not in os.environ:
		os.environ["DB_HOST"] = "database"
	if "DB_PORT" not in os.environ:
		os.environ["DB_PORT"] = "3306"
	if "DB_USER" not in os.environ:
		os.environ["DB_USER"] = "mailu"
	if "DB_PASSWORD" not in os.environ:
		os.environ["DB_PASSWORD"] = "mailu"
	if "DB_DATABASE" not in os.environ:
		os.environ["DB_DATABASE"] = "mailu"
else:
	os.environ["DB_TYPE"] = "sqlite"

convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

# Actual startup script
os.environ["FRONT_ADDRESS"] = socket.gethostbyname("front")
if os.environ["WEBMAIL"] != "none":
	os.environ["WEBMAIL_ADDRESS"] = socket.gethostbyname("webmail")

for dovecot_file in glob.glob("/conf/*.conf"):
    convert(dovecot_file, os.path.join("/etc/dovecot", os.path.basename(dovecot_file)))

for maps_file in glob.glob("/conf/" + os.environ["DB_TYPE"] + "/*"):
	convert(maps_file, os.path.join("/etc/dovecot", os.path.basename(maps_file)))

# Run dovecot
os.system("chown -R mail:mail /mail /var/lib/dovecot")
os.execv("/usr/sbin/dovecot", ["dovecot", "-c", "/etc/dovecot/dovecot.conf", "-F"])
