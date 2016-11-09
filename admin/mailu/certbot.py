from mailu import app, scheduler

import subprocess
import os


def certbot_command(subcommand, *args):
    """ Run a certbot command while specifying the standard parameters.
    """
    command = [
        "certbot", subcommand,
        "-n",
        "--work-dir", "/tmp",
        "--logs-dir", "/tmp",
        "--config-dir", app.config["CERTS_PATH"],
        *args
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    return result


def certbot_install(domain):
    """ Install certificates for the given domain. Return True if a reload
    is required.
    """
    must_reload = False
    path = app.config["CERTS_PATH"]
    cert = os.path.join(path, "cert.pem")
    key = os.path.join(path, "key.pem")
    live_cert = os.path.join(path, "live", domain, "fullchain.pem")
    live_key = os.path.join(path, "live", domain, "privkey.pem")
    if not os.path.islink(cert) or os.readlink(cert) != live_cert:
        must_reload = True
        os.unlink(cert)
        os.symlink(live_cert, cert)
    if not os.path.islink(key) or os.readlink(key) != live_key:
        must_reload = True
        os.unlink(key)
        os.symlink(live_key, key)
    return must_reload


@scheduler.scheduled_job('date')
@scheduler.scheduled_job('cron', hour=2, minute=0)
def generate_cert():
    print("Generating TLS certificates using Certbot")
    domain = app.config["DOMAIN"]
    email = "{}@{}".format(app.config["POSTMASTER"], domain)
    result = certbot_command(
        "certonly",
        "--standalone",
        "--agree-tos",
        "--preferred-challenges", "http",
        "--email", email,
        "-d", domain,
        # The port is hardcoded in the nginx image as well, we should find
        # a more suitable way to go but this will do until we have a proper
        # daemon handling certbot stuff
        "--http-01-port", "8081"
    )
    if result.returncode:
        print("Error while generating certificates:\n{}".format(
            result.stdout.decode("utf8") + result.stdout.decode("utf8")))
    else:
        print("Successfully generated or renewed TLS certificates")
        must_reload = certbot_install(domain)
        
