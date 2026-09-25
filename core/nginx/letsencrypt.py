#!/usr/bin/env python3

import logging as log
import os
import requests
import secrets
import socket
import stat
import sys
import subprocess
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_private_key

log.basicConfig(stream=sys.stderr, level="WARNING")
hostname_list = tuple(dict.fromkeys(
    host.strip() for host in os.environ['HOSTNAMES'].split(',') if host.strip()
))
renewed_marker = "/tmp/mailu-certificate-renewed"
renewal_required_marker = "/tmp/mailu-renewal-required"
deploy_marker = "/tmp/mailu-deploy-pending"

command = [
    "certbot",
    "-n", "--agree-tos", # non-interactive
    "-d", "",
    "-m", "{}@{}".format(os.environ["POSTMASTER"], os.environ["DOMAIN"]),
    "certonly", "--standalone",
    "--cert-name", "mailu",
    "--preferred-challenges", "http", "--http-01-port", "8008",
    "--keep-until-expiring",
    "--key-type", "rsa",
    "--renew-with-new-domains",
    "--config-dir", "/certs/letsencrypt",
    "--deploy-hook", f"touch {renewed_marker}"
]
command2 = [
    "certbot",
    "-n", "--agree-tos", # non-interactive
    "-d", "",
    "-m", "{}@{}".format(os.environ["POSTMASTER"], os.environ["DOMAIN"]),
    "certonly", "--standalone",
    "--cert-name", "mailu-ecdsa",
    "--preferred-challenges", "http", "--http-01-port", "8008",
    "--keep-until-expiring",
    "--key-type", "ecdsa",
    "--renew-with-new-domains",
    "--config-dir", "/certs/letsencrypt",
    "--deploy-hook", f"touch {renewed_marker}"
]

required_files = (
    "/certs/letsencrypt/live/mailu/fullchain.pem",
    "/certs/letsencrypt/live/mailu/privkey.pem",
    "/certs/letsencrypt/live/mailu-ecdsa/fullchain.pem",
    "/certs/letsencrypt/live/mailu-ecdsa/privkey.pem",
)
keypairs = (required_files[0], required_files[1]), (required_files[2], required_files[3])
renewal_configs = (
    "/certs/letsencrypt/renewal/mailu.conf",
    "/certs/letsencrypt/renewal/mailu-ecdsa.conf",
)


def remove_legacy_post_hooks():
    for renewal_config in renewal_configs:
        if not os.path.exists(renewal_config):
            continue
        with open(renewal_config) as config_file:
            lines = config_file.readlines()
        filtered_lines = [
            line for line in lines if line.partition("=")[0].strip() != "post_hook"
        ]
        if filtered_lines == lines:
            continue
        temporary_config = f"{renewal_config}.mailu"
        with open(temporary_config, "w") as config_file:
            config_file.writelines(filtered_lines)
        os.chmod(temporary_config, stat.S_IMODE(os.stat(renewal_config).st_mode))
        os.replace(temporary_config, renewal_config)


def certificate_state():
    now = datetime.now(timezone.utc)
    due = False
    for fullchain, private_key in keypairs:
        if not os.path.exists(fullchain) or not os.path.exists(private_key):
            return False, True
        try:
            with open(fullchain, "rb") as chain_file:
                certificate = x509.load_pem_x509_certificates(chain_file.read())[0]
            with open(private_key, "rb") as key_file:
                key = load_pem_private_key(key_file.read(), password=None)
        except (OSError, ValueError, IndexError, TypeError, UnsupportedAlgorithm):
            return False, True
        certificate_key = certificate.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo
        )
        private_public_key = key.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo
        )
        if certificate_key != private_public_key:
            return False, True
        if certificate.not_valid_after_utc <= now:
            return False, True
        lifetime = certificate.not_valid_after_utc - certificate.not_valid_before_utc
        if now >= certificate.not_valid_after_utc - lifetime / 3:
            due = True
    return True, due


def reachable_hostnames():
    token = secrets.token_urlsafe(32)
    challenge_path = f"/.well-known/acme-challenge/{token}"
    response_body = token.encode("ascii")

    class ChallengeHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != challenge_path:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def log_message(self, _format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 8008), ChallengeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    session = requests.Session()
    session.trust_env = False
    try:
        reachable = set()
        for attempt in range(3):
            for hostname in hostname_list:
                if hostname in reachable:
                    continue
                try:
                    addresses = tuple(dict.fromkeys(
                        (family, sockaddr[0])
                        for family, _, _, _, sockaddr in socket.getaddrinfo(
                            hostname, 80, type=socket.SOCK_STREAM
                        )
                        if family in (socket.AF_INET, socket.AF_INET6)
                    ))
                except socket.gaierror as error:
                    log.warning("Cannot resolve %s for HTTP-01: %s", hostname, error)
                    continue
                successful_address = False
                invalid_response = False
                for family, address in addresses:
                    url_address = f"[{address}]" if family == socket.AF_INET6 else address
                    target = f"http://{url_address}{challenge_path}"
                    try:
                        response = session.get(
                            target,
                            headers={"Host": hostname},
                            allow_redirects=False,
                            timeout=10,
                        )
                    except requests.RequestException as error:
                        log.warning(
                            "Cannot reach the HTTP-01 challenge for %s via %s: %s",
                            hostname,
                            address,
                            error,
                        )
                        continue
                    valid_response = response.status_code == 200 and response.content == response_body
                    if not valid_response:
                        invalid_response = True
                        log.warning(
                            "The HTTP-01 challenge for %s via %s returned status %s or an unexpected body",
                            hostname,
                            address,
                            response.status_code,
                        )
                    else:
                        successful_address = True
                if successful_address and not invalid_response:
                    reachable.add(hostname)
            if len(reachable) == len(hostname_list):
                break
            if attempt < 2:
                time.sleep(5)
        for hostname in set(hostname_list) - reachable:
            log.error("Excluding %s because its HTTP-01 challenge is not reachable", hostname)
        return tuple(hostname for hostname in hostname_list if hostname in reachable)
    finally:
        session.close()
        server.shutdown()
        thread.join()
        server.server_close()

# Wait for nginx to start
remove_legacy_post_hooks()
time.sleep(5)

# Run certbot every day
while True:
    certificates_ready = all(os.path.exists(path) for path in required_files)
    if os.path.exists(deploy_marker) and certificates_ready:
        certificates_valid, _ = certificate_state()
        if not certificates_valid:
            os.remove(deploy_marker)
        elif subprocess.call(["/config.py"]) == 0:
            os.remove(deploy_marker)
            for marker in (renewed_marker, renewal_required_marker):
                if os.path.exists(marker):
                    os.remove(marker)
        else:
            time.sleep(3600)
            continue

    while True:
        try:
            reachable = reachable_hostnames()
        except OSError as error:
            log.error("Cannot start the local HTTP-01 probe server: %s", error)
            reachable = ()
        if reachable:
            break
        log.critical("Port 80 must forward at least one hostname to Mailu before Let's Encrypt can be used")
        time.sleep(60)

    certificates_valid, renewal_due = certificate_state()
    if len(reachable) != len(hostname_list) and certificates_valid and not renewal_due:
        log.error("Keeping the current certificates until all hostnames are reachable or renewal is due")
        time.sleep(3600)
        continue

    domains = ','.join(reachable)
    command[command.index("-d") + 1] = domains
    command2[command2.index("-d") + 1] = domains
    try:
        rsa_status = subprocess.call(command, timeout=3600)
        ecdsa_status = subprocess.call(command2, timeout=3600)
    except subprocess.TimeoutExpired:
        log.exception("Certbot did not finish within one hour")
        time.sleep(3600)
        continue
    certificates_ready = all(os.path.exists(path) for path in required_files)
    if rsa_status != 0 or ecdsa_status != 0 or not certificates_ready:
        time.sleep(3600)
        continue
    if os.path.exists(renewed_marker) or os.path.exists(renewal_required_marker):
        try:
            subprocess.run(["/config.py"], check=True)
        except subprocess.CalledProcessError:
            certificates_valid, _ = certificate_state()
            if os.path.exists(renewed_marker) or certificates_valid:
                with open(deploy_marker, "a"):
                    pass
            time.sleep(3600)
            continue
        for marker in (renewed_marker, renewal_required_marker, deploy_marker):
            if os.path.exists(marker):
                os.remove(marker)
    time.sleep(86400)
