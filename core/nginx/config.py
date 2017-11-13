#!/usr/bin/python

import jinja2
import os

convert = lambda src, dst, args: open(dst, "w").write(jinja2.Template(open(src).read()).render(**args))

args = os.environ.copy()

# Get the first DNS server
with open("/etc/resolv.conf") as handle:
    content = handle.read().split()
    args["RESOLVER"] = content[content.index("nameserver") + 1]


# TLS configuration
args["TLS"] = {
    "cert": ("/certs/cert.pem", "/certs/key.pem"),
    "mail": ("/certs/cert.pem", "/certs/key.pem"),
    "letsencrypt": ("/certs/letsencrypt/live/mailu/fullchain.pem",
        "/certs/letsencrypt/live/mailu/privkey.pem"),
    "notls": None
}[args["TLS_FLAVOR"]]

if args["TLS"] and not all(os.path.exists(file_path) for file_path in args["TLS"]):
    print("Missing cert or key file, disabling TLS")
    args["TLS_ERROR"] = "yes"


# Build final configuration paths
convert("/conf/tls.conf", "/etc/nginx/tls.conf", args)
convert("/conf/nginx.conf", "/etc/nginx/nginx.conf", args)
os.system("nginx -s reload")
