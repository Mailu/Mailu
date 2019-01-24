#!/usr/bin/python3

import jinja2
import os
import socket
import glob
import shutil
import tenacity
import multiprocessing
import logging as log
import sys

from tenacity import retry
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

def convert(src, dst):
    logger = log.getLogger("convert()")
    logger.debug("Source: %s, Destination: %s", src, dst)
    open(dst, "w").write(jinja2.Template(open(src).read()).render(**os.environ))

@retry(
    stop=tenacity.stop_after_attempt(100),
    wait=tenacity.wait_random(min=2, max=5),
    before=tenacity.before_log(log.getLogger("tenacity.retry"), log.DEBUG),
    before_sleep=tenacity.before_sleep_log(log.getLogger("tenacity.retry"), log.INFO),
    after=tenacity.after_log(log.getLogger("tenacity.retry"), log.DEBUG)
    )
def resolve(hostname):
    logger = log.getLogger("resolve()")
    logger.info(hostname)
    return socket.gethostbyname(hostname)

# Actual startup script
os.environ["FRONT_ADDRESS"] = resolve(os.environ.get("FRONT_ADDRESS", "front"))
os.environ["ADMIN_ADDRESS"] = resolve(os.environ.get("ADMIN_ADDRESS", "admin"))
os.environ["HOST_ANTISPAM"] = os.environ.get("HOST_ANTISPAM", "antispam:11332")
os.environ["HOST_LMTP"] = os.environ.get("HOST_LMTP", "imap:2525")

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

convert("/conf/rsyslog.conf", "/etc/rsyslog.conf")

# Run Podop and Postfix
multiprocessing.Process(target=start_podop).start()
if os.path.exists("/var/run/rsyslogd.pid"):
    os.remove("/var/run/rsyslogd.pid")
os.system("/usr/lib/postfix/post-install meta_directory=/etc/postfix create-missing")
os.system("/usr/lib/postfix/master &")
os.execv("/usr/sbin/rsyslogd", ["rsyslogd", "-n"])
