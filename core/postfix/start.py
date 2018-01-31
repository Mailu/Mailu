#!/usr/bin/python

import jinja2
import os
import socket
import glob
import shutil
	
convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

# Actual startup script
os.environ["FRONT_ADDRESS"] = socket.gethostbyname(os.environ.get("FRONT_ADDRESS", "front"))
os.environ["HOST_ANTISPAM"] = os.environ.get("HOST_ANTISPAM", "antispam:11332")
os.environ["HOST_LMTP"] = os.environ.get("HOST_LMTP", "imap:2525")

for postfix_file in glob.glob("/conf/*.cf"):
    convert(postfix_file, os.path.join("/etc/postfix", os.path.basename(postfix_file)))

if os.path.exists("/overrides/postfix.cf"):
    for line in open("/overrides/postfix.cf").read().strip().split("\n"):
        os.system('postconf -e "{}"'.format(line))

if os.path.exists("/overrides/postfix.master"):
    for line in open("/overrides/postfix.master").read().strip().split("\n"):
        os.system('postconf -Me "{}"'.format(line))

for map_file in glob.glob("/overrides/*.map"):
    destination = os.path.join("/etc/postfix", os.path.basename(map_file))
    shutil.copyfile(map_file, destination)
    os.system("postmap {}".format(destination))
    os.remove(destination)

convert("/conf/rsyslog.conf", "/etc/rsyslog.conf")

# Run postfix
if os.path.exists("/var/run/rsyslogd.pid"):
    os.remove("/var/run/rsyslogd.pid")
os.system("/usr/lib/postfix/post-install meta_directory=/etc/postfix create-missing")
os.system("/usr/lib/postfix/master &")
os.execv("/usr/sbin/rsyslogd", ["rsyslogd", "-n"])
