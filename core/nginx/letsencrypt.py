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
    "--key-type", "ecdsa",
    "--config-dir", "/certs/letsencrypt",
    "--post-hook", "/config.py"
]

def format_for_nginx(fullchain, output):
    """ nginx doesn't need the "compat"
    """
    certs = []
    with open(fullchain, 'r') as pem:
        cert = ''
        for line in pem:
            cert += line
            if '-----END CERTIFICATE-----' in line:
                certs += [cert]
                cert = ''
    with open(output, 'w') as pem:
        for cert in certs[:-1]:
            pem.write(cert)

# Wait for nginx to start
time.sleep(5)

# Run certbot every hour
while True:
    subprocess.call(command)
    format_for_nginx('/certs/letsencrypt/live/mailu/fullchain.pem', '/certs/letsencrypt/live/mailu/nginx-chain.pem')
    subprocess.call(command2)
    format_for_nginx('/certs/letsencrypt/live/mailu-ecdsa/fullchain.pem', '/certs/letsencrypt/live/mailu-ecdsa/nginx-chain.pem')
    time.sleep(3600)

