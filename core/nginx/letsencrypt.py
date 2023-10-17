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
    subprocess.call(command2)
    time.sleep(86400)
