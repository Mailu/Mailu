#!/usr/bin/python

import jinja2
import os

convert = lambda src, dst, args: open(dst, "w").write(jinja2.Template(open(src).read()).render(**args))

args = os.environ.copy()

# Get the first DNS server
with open("/etc/resolv.conf") as handle:
    content = handle.read().split()
    args["RESOLVER"] = content[content.index("nameserver") + 1]

if "HOST_WEBMAIL" not in args:
    args["HOST_WEBMAIL"] = "webmail"
if "HOST_ADMIN" not in args:
    args["HOST_ADMIN"] = "admin"
if "HOST_WEBDAV" not in args:
    args["HOST_WEBDAV"] = "webdav:5232"
if "HOST_ANTISPAM" not in args:
    args["HOST_ANTISPAM"] = "antispam:11334"

# TLS configuration
args["TLS"] = {
    "cert": ("/certs/cert.pem", "/certs/key.pem"),
    "letsencrypt": ("/certs/letsencrypt/live/mailu/fullchain.pem",
        "/certs/letsencrypt/live/mailu/privkey.pem"),
    "mail": ("/certs/cert.pem", "/certs/key.pem"),
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
if os.path.exists("/var/log/nginx.pid"):
    os.system("nginx -s reload")
