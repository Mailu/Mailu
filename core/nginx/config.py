#!/usr/bin/env python3

import os
import logging as log
import sys
from socrate import system, conf

args = system.set_env()
log.basicConfig(stream=sys.stderr, level=args.get("LOG_LEVEL", "WARNING"))

args['TLS_PERMISSIVE'] = str(args.get('TLS_PERMISSIVE')).lower() not in ('false', 'no')

# Get the first DNS server
with open("/etc/resolv.conf") as handle:
    content = handle.read().split()
    resolver = content[content.index("nameserver") + 1]
    args["RESOLVER"] = f"[{resolver}]" if ":" in resolver else resolver

# TLS configuration
cert_name = args.get("TLS_CERT_FILENAME", "cert.pem")
keypair_name = args.get("TLS_KEYPAIR_FILENAME", "key.pem")
args["TLS"] = {
    "cert": ("/certs/%s" % cert_name, "/certs/%s" % keypair_name),
    "letsencrypt": ("/certs/letsencrypt/live/mailu/nginx-chain.pem",
        "/certs/letsencrypt/live/mailu/privkey.pem", "/certs/letsencrypt/live/mailu-ecdsa/nginx-chain.pem", "/certs/letsencrypt/live/mailu-ecdsa/privkey.pem"),
    "mail": ("/certs/%s" % cert_name, "/certs/%s" % keypair_name),
    "mail-letsencrypt": ("/certs/letsencrypt/live/mailu/nginx-chain.pem",
        "/certs/letsencrypt/live/mailu/privkey.pem", "/certs/letsencrypt/live/mailu-ecdsa/nginx-chain.pem", "/certs/letsencrypt/live/mailu-ecdsa/privkey.pem"),
    "notls": None
}[args["TLS_FLAVOR"]]

def format_for_nginx(fullchain, output):
    """ We may want to strip ISRG Root X1 out """
    if not os.path.exists(fullchain):
        return
    split = '-----END CERTIFICATE-----\n'
    with open(fullchain, 'r') as pem:
        certs = [f'{cert}{split}' for cert in pem.read().split(split) if cert]
    if len(certs)>2 and args.get('LETSENCRYPT_SHORTCHAIN'):
        del certs[-1]
    with open(output, 'w') as pem:
        pem.write(''.join(certs))

if args['TLS_FLAVOR'] in ['letsencrypt', 'mail-letsencrypt']:
    format_for_nginx('/certs/letsencrypt/live/mailu/fullchain.pem', '/certs/letsencrypt/live/mailu/nginx-chain.pem')
    format_for_nginx('/certs/letsencrypt/live/mailu-ecdsa/fullchain.pem', '/certs/letsencrypt/live/mailu-ecdsa/nginx-chain.pem')

if args["TLS"] and not all(os.path.exists(file_path) for file_path in args["TLS"]):
    print("Missing cert or key file, disabling TLS")
    args["TLS_ERROR"] = "yes"

# Build final configuration paths
conf.jinja("/conf/tls.conf", args, "/etc/nginx/tls.conf")
conf.jinja("/conf/proxy.conf", args, "/etc/nginx/proxy.conf")
conf.jinja("/conf/nginx.conf", args, "/etc/nginx/nginx.conf")
if os.path.exists("/var/run/nginx.pid"):
    os.system("nginx -s reload")
conf.jinja("/dovecot_conf/login.lua", args, "/etc/dovecot/login.lua")
conf.jinja("/dovecot_conf/proxy.conf", args, "/etc/dovecot/proxy.conf")
if os.path.exists("/run/dovecot/master.pid"):
    os.system("doveadm reload")
