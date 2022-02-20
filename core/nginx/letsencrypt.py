#!/usr/bin/env python3

import logging as log
import os
import requests
import sys
import subprocess
import time
from threading import Thread
from http.server import HTTPServer, SimpleHTTPRequestHandler

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

<<<<<<< HEAD
<<<<<<< HEAD
=======
def format_for_nginx(fullchain, output):
    """ We may want to strip ISRG Root X1 out
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
        for cert in certs[:-1] if len(certs)>2 and os.getenv('LETSENCRYPT_SHORTCHAIN', default="False") else certs:
            pem.write(cert)

def add_DANE_pin(chain, output):
    with open(output, 'w') as pem:
        with open(chain, 'r') as chain:
            for line in chain:
                pem.write(line)
        with open('/etc/ssl/certs/ca-cert-ISRG_Root_X1.pem', 'r') as isrgx1:
            for line in isrgx1:
                pem.write(line)

>>>>>>> e4a32b55 (Send ISRG_X1 on port 25, make DANE pin that)
=======
>>>>>>> 0816cb94 (simplify as per ghostwheel42's suggestion)
# Wait for nginx to start
time.sleep(5)

class MyRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/.well-known/acme-challenge/testing':
            self.send_response(204)
        else:
            self.send_response(404)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()

def serve_one_request():
    with HTTPServer(("127.0.0.1", 8008), MyRequestHandler) as server:
        server.handle_request()

# Run certbot every day
while True:
    while True:
        hostname = os.environ['HOSTNAMES'].split(',')[0]
        target = f'http://{hostname}/.well-known/acme-challenge/testing'
        thread = Thread(target=serve_one_request)
        thread.start()
        r = requests.get(target)
        if r.status_code != 204:
            log.critical(f"Can't reach {target}!, please ensure it's fixed or change the TLS_FLAVOR.")
            time.sleep(5)
        else:
            break
        thread.join()

    subprocess.call(command)
<<<<<<< HEAD
<<<<<<< HEAD
    subprocess.call(command2)
=======
    format_for_nginx('/certs/letsencrypt/live/mailu/fullchain.pem', '/certs/letsencrypt/live/mailu/nginx-chain.pem')
    add_DANE_pin('/certs/letsencrypt/live/mailu/chain.pem', '/certs/letsencrypt/live/mailu/nginx-chain-DANE.pem')
    subprocess.call(command2)
    format_for_nginx('/certs/letsencrypt/live/mailu-ecdsa/fullchain.pem', '/certs/letsencrypt/live/mailu-ecdsa/nginx-chain.pem')
    add_DANE_pin('/certs/letsencrypt/live/mailu-ecdsa/chain.pem', '/certs/letsencrypt/live/mailu-ecdsa/nginx-chain-DANE.pem')
>>>>>>> e4a32b55 (Send ISRG_X1 on port 25, make DANE pin that)
=======
    subprocess.call(command2)
>>>>>>> 0816cb94 (simplify as per ghostwheel42's suggestion)
    time.sleep(86400)
