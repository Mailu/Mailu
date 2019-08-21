#!/usr/bin/python3

import os
import glob
import shutil
import multiprocessing
import logging as log
import sys

from podop   import run_server
from socrate import system, conf

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

def start_podop():
    os.setuid(100)
    url = "http://" + os.environ["ADMIN_ADDRESS"] + "/internal/postfix/"
    # TODO: Remove verbosity setting from Podop?
    run_server(0, "postfix", "/tmp/podop.socket", [
		("transport", "url", url + "transport/§"),
		("alias", "url", url + "alias/§"),
		("domain", "url", url + "domain/§"),
        ("mailbox", "url", url + "mailbox/§"),
        ("senderaccess", "url", url + "sender/access/§"),
        ("senderlogin", "url", url + "sender/login/§")
    ])

# Actual startup script
os.environ["FRONT_ADDRESS"] = system.resolve_address(os.environ.get("FRONT_ADDRESS", "front"))
os.environ["ADMIN_ADDRESS"] = system.resolve_address(os.environ.get("ADMIN_ADDRESS", "admin"))
os.environ["HOST_ANTISPAM"] = system.resolve_address(os.environ.get("HOST_ANTISPAM", "antispam:11332"))
os.environ["HOST_LMTP"] = system.resolve_address(os.environ.get("HOST_LMTP", "imap:2525"))

for postfix_file in glob.glob("/conf/*.cf"):
    conf.jinja(postfix_file, os.environ, os.path.join("/etc/postfix", os.path.basename(postfix_file)))

if os.path.exists("/overrides/postfix.cf"):
    for line in open("/overrides/postfix.cf").read().strip().split("\n"):
        os.system('postconf -e "{}"'.format(line))

if os.path.exists("/overrides/postfix.master"):
    for line in open("/overrides/postfix.master").read().strip().split("\n"):
        os.system('postconf -Me "{}"'.format(line))

for map_file in glob.glob("/overrides/*.map"):
    destination = os.path.join("/etc/postfix", os.path.basename(map_file))
    shutil.copyfile(map_file, destination)
    os.system("postmap {}".format(destination))
    os.remove(destination)

if "RELAYUSER" in os.environ:
    path = "/etc/postfix/sasl_passwd"
    conf.jinja("/conf/sasl_passwd", os.environ, path)
    os.system("postmap {}".format(path))

# Run Podop and Postfix
multiprocessing.Process(target=start_podop).start()
os.system("/usr/libexec/postfix/post-install meta_directory=/etc/postfix create-missing")
os.system("postfix start-fg")
