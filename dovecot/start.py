#!/usr/bin/python

import jinja2
import os
import socket
import glob
	
convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

# Actual startup script
os.environ["FRONT_ADDRESS"] = socket.gethostbyname("front")

for postfix_file in glob.glob("/conf/*.cf"):
    convert(postfix_file, os.path.join("/etc/postfix", os.path.basename(postfix_file)))

convert("/conf/rsyslog.conf", "/etc/rsyslog.conf")

# Run postfix
os.system("chown -R mail:mail /mail /var/lib/dovecot")
os.execv("/usr/sbin/dovecot" ["dovecot", "-c", "/etc/dovecot/dovecot.conf", "-F"])
