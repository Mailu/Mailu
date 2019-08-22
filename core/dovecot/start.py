#!/usr/bin/env python3

import os
import glob
import multiprocessing

from podop import run_server
from socrate import system, conf

system.set_env(log_filters=[r'Error\: SSL context initialization failed, disabling SSL\: Can\'t load SSL certificate \(ssl_cert setting\)\: The certificate is empty$'])

def start_podop():
    system.drop_privs_to('mail')
    url = "http://" + os.environ["ADMIN_ADDRESS"] + ":8080/internal/dovecot/§"
    run_server(0, "dovecot", "/tmp/podop.socket", [
		("quota", "url", url ),
		("auth", "url", url),
		("sieve", "url", url),
    ])

# Actual startup script
<<<<<<< HEAD
=======
os.environ["FRONT_ADDRESS"] = system.resolve_address(os.environ.get("HOST_FRONT", "front"))
os.environ["REDIS_ADDRESS"] = system.resolve_address(os.environ.get("HOST_REDIS", "redis"))
os.environ["ADMIN_ADDRESS"] = system.resolve_address(os.environ.get("HOST_ADMIN", "admin"))
os.environ["ANTISPAM_ADDRESS"] = system.resolve_address(os.environ.get("HOST_ANTISPAM", "antispam:11334"))
if os.environ["WEBMAIL"] != "none":
    os.environ["WEBMAIL_ADDRESS"] = system.resolve_address(os.environ.get("HOST_WEBMAIL", "webmail"))

>>>>>>> 05ea4474 (make `ANTIVIRUS_ADDRESS` consistent with #940)
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
cmd = ['/usr/sbin/dovecot', '-c', '/etc/dovecot/dovecot.conf', '-F']
system.run_process_and_forward_output(cmd)
