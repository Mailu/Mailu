#!/usr/bin/env python3

import os
import glob
import multiprocessing
import logging as log
import sys
from pwd import getpwnam

from podop import run_server
from socrate import system, conf

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))
system.set_env()

def start_podop():
    id_mail = getpwnam('mail')
    os.setgid(id_mail.pw_gid)
    os.setuid(id_mail.pw_uid)
    url = "http://" + os.environ["ADMIN_ADDRESS"] + "/internal/dovecot/§"
    run_server(0, "dovecot", "/tmp/podop.socket", [
		("quota", "url", url ),
		("auth", "url", url),
		("sieve", "url", url),
    ])

# Actual startup script
for dovecot_file in glob.glob("/conf/*.conf"):
    conf.jinja(dovecot_file, os.environ, os.path.join("/etc/dovecot", os.path.basename(dovecot_file)))

os.makedirs("/conf/bin", exist_ok=True)
for script_file in glob.glob("/conf/*.script"):
    out_file = os.path.join("/conf/bin/", os.path.basename(script_file).replace('.script',''))
    conf.jinja(script_file, os.environ, out_file)
    os.chmod(out_file, 0o555)

# Run Podop, then postfix
os.system("chown mail:mail /mail")
os.system("chown -R mail:mail /var/lib/dovecot /conf")

multiprocessing.Process(target=start_podop).start()
os.execv("/usr/sbin/dovecot", ["dovecot", "-c", "/etc/dovecot/dovecot.conf", "-F"])
