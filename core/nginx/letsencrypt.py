#!/usr/bin/env python3

import logging as log
import os
import requests
import sys
import subprocess
import time

log.basicConfig(stream=sys.stderr, level="WARNING")
hostnames = ','.join(set(host.strip() for host in os.environ['HOSTNAMES'].split(',')))

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
    "--post-hook", "/config.py"
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
    "--post-hook", "/config.py"
]

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

    subprocess.call(command)
    subprocess.call(command2)
    time.sleep(86400)
