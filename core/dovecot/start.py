#!/usr/bin/python3

import os
import stat
import glob
import multiprocessing
import logging as log
import sys

from podop   import run_server
from socrate import system, conf

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

def start_podop():
    os.setuid(8)
    url = "http://" + os.environ["ADMIN_ADDRESS"] + "/internal/dovecot/§"
    run_server(0, "dovecot", "/tmp/podop.socket", [
		("quota", "url", url ),
		("auth", "url", url),
		("sieve", "url", url),
    ])

# Actual startup script

os.environ["FRONT_ADDRESS"] = system.get_host_address_from_environment("FRONT", "front")
os.environ["REDIS_ADDRESS"] = system.get_host_address_from_environment("REDIS", "redis")
os.environ["ADMIN_ADDRESS"] = system.get_host_address_from_environment("ADMIN", "admin")
os.environ["ANTISPAM_ADDRESS"] = system.get_host_address_from_environment("ANTISPAM", "antispam:11334")
if os.environ["WEBMAIL"] != "none":
    os.environ["WEBMAIL_ADDRESS"] = system.get_host_address_from_environment("WEBMAIL", "webmail")

for dovecot_file in glob.glob("/conf/*.conf"):
    conf.jinja(dovecot_file, os.environ, os.path.join("/etc/dovecot", os.path.basename(dovecot_file)))

try:
    os.mkdir("/conf/bin")
except FileExistsError:
    pass
for script_file in glob.glob("/conf/*.script"):
    out_file = os.path.join("/conf/bin/", os.path.basename(script_file).replace('.script',''))
    conf.jinja(script_file, os.environ, out_file)
    os.chmod(out_file, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

# Run Podop, then postfix
multiprocessing.Process(target=start_podop).start()
os.system("chown mail:mail /mail")
os.system("chown -R mail:mail /var/lib/dovecot /conf")
os.execv("/usr/sbin/dovecot", ["dovecot", "-c", "/etc/dovecot/dovecot.conf", "-F"])
