#!/usr/bin/env python3

import os
import glob

from socrate import system, conf, supervisor

log_filters = [
    rb'Error\: SSL context initialization failed, disabling SSL\: Couldn\'t initialize SSL server context\: Can\'t load SSL certificate \(ssl_server_cert_file setting\)\: The certificate is empty$',
]
env = system.set_env()

# Actual startup script
context = dict(os.environ, FULL_TEXT_SEARCH_ATTACHMENTS=env.get('FULL_TEXT_SEARCH_ATTACHMENTS', False))

for dovecot_file in glob.glob("/conf/*.conf"):
    conf.jinja(dovecot_file, context, os.path.join("/etc/dovecot", os.path.basename(dovecot_file)))
conf.jinja("/conf/login.lua", context, "/etc/dovecot/login.lua")

os.makedirs("/conf/bin", exist_ok=True)
for script_file in glob.glob("/conf/*.script"):
    out_file = os.path.join("/conf/bin/", os.path.basename(script_file).replace('.script',''))
    conf.jinja(script_file, context, out_file)
    os.chmod(out_file, 0o555)

supervisor.clean_environment()

# Run Podop, then postfix
os.system("chown mail:mail /mail")
os.system("chown -R mail:mail /var/lib/dovecot /conf")

supervisor.start([
    {"name": "podop", "command": ["python3", "-m", "podop.run_server", "dovecot"], "priority": 10},
    {"name": "dovecot", "command": ["/usr/sbin/dovecot", "-c", "/etc/dovecot/dovecot.conf", "-F"], "log_filters": log_filters, "priority": 20},
])
