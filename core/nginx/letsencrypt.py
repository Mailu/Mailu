#!/usr/bin/env python3

import logging as log
import os
import requests
import sys
import subprocess
import time

log.basicConfig(stream=sys.stderr, level="WARNING")
hostnames = ','.join(set(host.strip() for host in os.environ['HOSTNAMES'].split(',')))
deploy_marker = "/tmp/mailu-certificates-renewed"

command = [
    "certbot",
    "-n", "--agree-tos", # non-interactive
    "-d", hostnames, "--expand", "--allow-subset-of-names",
    "-m", "{}@{}".format(os.environ["POSTMASTER"], os.environ["DOMAIN"]),
    "certonly", "--standalone",
    "--cert-name", "mailu",
    "--preferred-challenges", "http", "--http-01-port", "8008",
    "--keep-until-expiring",
    "--allow-subset-of-names",
    "--key-type", "rsa",
    "--renew-with-new-domains",
    "--config-dir", "/certs/letsencrypt",
    "--deploy-hook", f"touch {deploy_marker}"
]
command2 = [
    "certbot",
    "-n", "--agree-tos", # non-interactive
    "-d", hostnames, "--expand", "--allow-subset-of-names",
    "-m", "{}@{}".format(os.environ["POSTMASTER"], os.environ["DOMAIN"]),
    "certonly", "--standalone",
    "--cert-name", "mailu-ecdsa",
    "--preferred-challenges", "http", "--http-01-port", "8008",
    "--keep-until-expiring",
    "--allow-subset-of-names",
    "--key-type", "ecdsa",
    "--renew-with-new-domains",
    "--config-dir", "/certs/letsencrypt",
    "--deploy-hook", f"touch {deploy_marker}"
]

required_files = (
    "/certs/letsencrypt/live/mailu/fullchain.pem",
    "/certs/letsencrypt/live/mailu/privkey.pem",
    "/certs/letsencrypt/live/mailu-ecdsa/fullchain.pem",
    "/certs/letsencrypt/live/mailu-ecdsa/privkey.pem",
)

# Wait for nginx to start
time.sleep(5)

# Run certbot every day
while True:
    while True:
        hostname = os.environ['HOSTNAMES'].split(',')[0]
        target = f'http://{hostname}/.well-known/acme-challenge/testing'
        try:
            r = requests.get(target)
            if r.status_code != 204:
                log.critical(f"Can't reach {target}!, please ensure it's fixed or change the TLS_FLAVOR.")
                time.sleep(5)
            else:
                break
        except Exception as e:
            log.error(f"Exception while fetching {target}!", exc_info = e)
            time.sleep(15)

    rsa_status = subprocess.call(command)
    ecdsa_status = subprocess.call(command2)
    if (
        rsa_status == 0
        and ecdsa_status == 0
        and os.path.exists(deploy_marker)
        and all(os.path.exists(path) for path in required_files)
    ):
        if subprocess.call(["/config.py"]) == 0:
            os.remove(deploy_marker)
    time.sleep(86400)
