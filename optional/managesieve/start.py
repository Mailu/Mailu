#!/usr/bin/python

import jinja2
import os
import socket
import glob

convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

# Actual startup script
os.environ["FRONT_ADDRESS"] = socket.gethostbyname(os.environ.get("FRONT_ADDRESS", "front"))
os.environ["DOVECOT_ADDRESS"] = socket.gethostbyname(os.environ.get("DOVECOT_ADDRESS", "imap"))

for dovecot_file in glob.glob("/conf/*"):
    convert(dovecot_file, os.path.join("/etc/dovecot", os.path.basename(dovecot_file)))

# Run postfix
os.system("chown -R mail:mail /var/lib/dovecot")
os.execv("/usr/sbin/dovecot", ["dovecot", "-c", "/etc/dovecot/dovecot.conf", "-F"])
