#!/usr/bin/python

import jinja2
import os
import socket
	
convert = lambda src, dst, args: open(dst, "w").write(jinja2.Template(open(src).read()).render(**args))

args = os.environ.copy()

if "ADMIN_ADDRESS" not in os.environ:
    args["ADMIN_ADDRESS"] = socket.gethostbyname("admin")

args["TLS"] = {
    "cert": ("/certs/cert.pem", "/certs/key.pem"),
    "letsencrypt": ("/certs/letsencrypt/live/mailu/fullchain.pem",
        "/certs/letsencrypt/live/mailu/privkey.pem"),
    "notls": None
}[args["TLS_FLAVOR"]]

if args["TLS"] and not all(os.path.exists(file_path) for file_path in args["TLS"]):
    print("Missing cert or key file, disabling TLS")
    args["TLS_ERROR"] = "yes"


convert("/conf/nginx.conf", "/etc/nginx/nginx.conf", args)
os.system("nginx -s reload")
