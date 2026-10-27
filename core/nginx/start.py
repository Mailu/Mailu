#!/usr/bin/env python3

import os
import subprocess
from socrate import system, supervisor

log_filters = [
    rb'could not be resolved \(\d\: [^\)]+\) while in resolving client address, client\: [^,]+, server: [^\:]+\:(25|110|143|587|465|993|995)$'
]
system.set_env()
supervisor.clean_environment()

subprocess.run(["/config.py", "--bootstrap"], check=True)
programs = [
    {"name": "dovecot", "command": ["/usr/sbin/dovecot", "-c", "/etc/dovecot/proxy.conf", "-F"]},
    {"name": "nginx", "command": ["/usr/sbin/nginx", "-g", "daemon off;"], "log_filters": log_filters},
]
if os.environ["TLS_FLAVOR"] in ["letsencrypt", "mail-letsencrypt"]:
    programs.append({"name": "certbot-renewal", "command": ["/letsencrypt.py"]})
elif os.environ["TLS_FLAVOR"] in ["mail", "cert"]:
    programs.append({"name": "certificate-watcher", "command": ["/certwatcher.py"]})

supervisor.start(programs)
