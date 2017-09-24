#!/usr/bin/python

import jinja2
import os
import socket
	
convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

# Actual startup script
if "ADMIN_ADDRESS" not in os.environ:
    os.environ["ADMIN_ADDRESS"] = socket.gethostbyname("admin")
convert("/conf/nginx.conf", "/etc/nginx/nginx.conf")
os.execv("/usr/sbin/nginx", ["nginx", "-g", "daemon off;"])
