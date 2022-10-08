#!/usr/bin/python3

import os
import time
import subprocess

command = [
    "certbot",
    "-n", "--agree-tos", # non-interactive
    "-d", os.environ["HOSTNAMES"],
    "-m", "{}@{}".format(os.environ["POSTMASTER"], os.environ["DOMAIN"]),
    "certonly", "--standalone",
    "--cert-name", "mailu",
    "--preferred-challenges", "http", "--http-01-port", "8008",
    "--keep-until-expiring",
    "--allow-subset-of-names",
    "--renew-with-new-domains",
    "--config-dir", "/certs/letsencrypt",
    "--post-hook", "/config.py"
]
command2 = [
    "certbot",
    "-n", "--agree-tos", # non-interactive
    "-d", os.environ["HOSTNAMES"],
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
    subprocess.call(command)
    subprocess.call(command2)
    time.sleep(86400)
