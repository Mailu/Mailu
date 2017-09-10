from mailu import app, scheduler, dockercli

import urllib3
import json
import os
import base64
import subprocess


def install_certs(domain):
    """ Extract certificates from the given domain and install them
    to the certificate path.
    """
    path = app.config["CERTS_PATH"]
    acme_path = os.path.join(path, "acme.json")
    key_path = os.path.join(path, "key.pem")
    cert_path = os.path.join(path, "cert.pem")
    if not os.path.exists(acme_path):
        print("Could not find traefik acme configuration")
        return
    with open(acme_path, "r") as handler:
        data = json.loads(handler.read())
    for item in data["DomainsCertificate"]["Certs"]:
        if domain == item["Domains"]["Main"]:
            cert = base64.b64decode(item["Certificate"]["Certificate"])
            key = base64.b64decode(item["Certificate"]["PrivateKey"])
            break
    else:
        print("Could not find the proper certificate from traefik")
        return
    if os.path.join(cert_path):
        with open(cert_path, "rb") as handler:
            if handler.read() == cert:
                return
    print("Installing the new certificate from traefik")
    with open(cert_path, "wb") as handler:
        handler.write(cert)
    with open(key_path, "wb") as handler:
        handler.write(key)


def restart_services():
    print("Reloading services using TLS")
    dockercli.reload("http", "smtp", "imap")


@scheduler.scheduled_job('date')
def create_dhparam():
    path = app.config["CERTS_PATH"]
    dhparam_path = os.path.join(path, "dhparam.pem")
    if not os.path.exists(dhparam_path):
        print("Creating DH params")
        subprocess.call(["openssl", "dhparam", "-out", dhparam_path, "2048"])
        restart_services()


@scheduler.scheduled_job('date')
@scheduler.scheduled_job('cron', day='*/4', hour=0, minute=0)
def refresh_certs():
    if not app.config["TLS_FLAVOR"] == "letsencrypt":
        return
    if not app.config["FRONTEND"] == "traefik":
        print("Letsencrypt certificates are compatible with traefik only")
        return
    print("Requesting traefik to make sure the certificate is fresh")
    hostname = app.config["HOSTNAME"]
    urllib3.PoolManager().request("GET", "https://{}".format(hostname))
    install_certs(hostname)
