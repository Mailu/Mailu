#!/usr/bin/env python3

import os
import glob
import multiprocessing
import logging as log
import sys

from podop import run_server
from socrate import system, conf

system.set_env(log_filters=r'Error\: SSL context initialization failed, disabling SSL\: Can\'t load SSL certificate \(ssl_cert setting\)\: The certificate is empty$')

def start_podop():
    system.drop_privs_to('mail')
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
os.system("rm -rf /run/dovecot/master.pid")

multiprocessing.Process(target=start_podop).start()
os.system("dovecot -c /etc/dovecot/dovecot.conf -F")
