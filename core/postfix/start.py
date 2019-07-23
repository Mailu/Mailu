#!/usr/bin/python3

import os
import glob
import shutil
import multiprocessing
import logging as log
import sys
from mailustart import resolve, convert

from podop import run_server

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
os.environ["FRONT_ADDRESS"] = resolve(os.environ.get("FRONT_ADDRESS", "front"))
os.environ["ADMIN_ADDRESS"] = resolve(os.environ.get("ADMIN_ADDRESS", "admin"))
os.environ["HOST_ANTISPAM"] = resolve(os.environ.get("HOST_ANTISPAM", "antispam:11332"))
os.environ["HOST_LMTP"] = resolve(os.environ.get("HOST_LMTP", "imap:2525"))

for postfix_file in glob.glob("/conf/*.cf"):
    convert(postfix_file, os.path.join("/etc/postfix", os.path.basename(postfix_file)))

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
    convert("/conf/sasl_passwd", path)
    os.system("postmap {}".format(path))

# Run Podop and Postfix
multiprocessing.Process(target=start_podop).start()
os.system("/usr/libexec/postfix/post-install meta_directory=/etc/postfix create-missing")
os.system("postfix start-fg")
