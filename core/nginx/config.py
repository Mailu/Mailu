#!/usr/bin/python3

import os
import logging as log
import sys
from mailustart import resolve, convert

args = os.environ.copy()

log.basicConfig(stream=sys.stderr, level=args.get("LOG_LEVEL", "WARNING"))

# Get the first DNS server
with open("/etc/resolv.conf") as handle:
    content = handle.read().split()
    args["RESOLVER"] = content[content.index("nameserver") + 1]

args["HOST_ADMIN"] = resolve(args.get("HOST_ADMIN", "admin"))
args["HOST_ANTISPAM"] = resolve(args.get("HOST_ANTISPAM", "antispam:11334"))
args["HOST_WEBMAIL"] = args.get("HOST_WEBMAIL", "webmail")
if args["WEBMAIL"] != "none":
    args["HOST_WEBMAIL"] = resolve(args.get("HOST_WEBMAIL"))
args["HOST_WEBDAV"] = args.get("HOST_WEBDAV", "webdav:5232")
if args["WEBDAV"] != "none":
    args["HOST_WEBDAV"] = resolve(args.get("HOST_WEBDAV"))

# TLS configuration
cert_name = os.getenv("TLS_CERT_FILENAME", default="cert.pem")
keypair_name = os.getenv("TLS_KEYPAIR_FILENAME", default="key.pem")
args["TLS"] = {
    "cert": ("/certs/%s" % cert_name, "/certs/%s" % keypair_name),
    "letsencrypt": ("/certs/letsencrypt/live/mailu/fullchain.pem",
        "/certs/letsencrypt/live/mailu/privkey.pem"),
    "mail": ("/certs/%s" % cert_name, "/certs/%s" % keypair_name),
    "mail-letsencrypt": ("/certs/letsencrypt/live/mailu/fullchain.pem",
        "/certs/letsencrypt/live/mailu/privkey.pem"),
    "notls": None
}[args["TLS_FLAVOR"]]

if args["TLS"] and not all(os.path.exists(file_path) for file_path in args["TLS"]):
    print("Missing cert or key file, disabling TLS")
    args["TLS_ERROR"] = "yes"

# Build final configuration paths
convert("/conf/tls.conf", "/etc/nginx/tls.conf", args)
convert("/conf/proxy.conf", "/etc/nginx/proxy.conf", args)
convert("/conf/nginx.conf", "/etc/nginx/nginx.conf", args)
if os.path.exists("/var/run/nginx.pid"):
    os.system("nginx -s reload")
