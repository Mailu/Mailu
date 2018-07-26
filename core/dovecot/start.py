#!/usr/bin/python3

import jinja2
import os
import socket
import glob
import multiprocessing

from podop import run_server


def start_podop():
    os.setuid(8)
    run_server(40, "dovecot", "/tmp/podop.socket", [
		("quota", "url", "http://admin/internal/dovecot/quota/§"),
		("auth", "url", "http://admin/internal/dovecot/auth/§"),
		("sieve", "url", "http://admin/internal/dovecot/sieve/§"),
    ])

convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

# Actual startup script
os.environ["FRONT_ADDRESS"] = socket.gethostbyname(os.environ.get("FRONT_ADDRESS", "front"))

for dovecot_file in glob.glob("/conf/*"):
    convert(dovecot_file, os.path.join("/etc/dovecot", os.path.basename(dovecot_file)))

# Run Podop, then postfix
multiprocessing.Process(target=start_podop).start()
os.system("chown -R mail:mail /mail /var/lib/dovecot")
os.execv("/usr/sbin/dovecot", ["dovecot", "-c", "/etc/dovecot/dovecot.conf", "-F"])
