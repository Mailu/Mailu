#!/usr/bin/python3

import jinja2
import os
import shutil

convert = lambda src, dst: open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

# Actual startup script
os.environ["FRONT_ADDRESS"] = os.environ.get("FRONT_ADDRESS", "front")
os.environ["IMAP_ADDRESS"] = os.environ.get("IMAP_ADDRESS", "imap")

base = "/data/_data_/_default_/"
shutil.rmtree(base + "domains/", ignore_errors=True)
os.makedirs(base + "domains", exist_ok=True)
os.makedirs(base + "configs", exist_ok=True)

convert("/default.ini", "/data/_data_/_default_/domains/default.ini")
convert("/config.ini", "/data/_data_/_default_/configs/config.ini")

os.execv("/usr/local/bin/apache2-foreground", ["apache2-foreground"])
