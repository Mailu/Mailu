#!/usr/bin/python3

import os
import glob
import shutil
import multiprocessing
import logging as log
import sys

from podop   import run_server
from pwd import getpwnam
from socrate import system, conf

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

def start_podop():
    os.setuid(getpwnam('postfix').pw_uid)
    os.mkdir('/dev/shm/postfix',mode=0o700)
    url = "http://" + os.environ["ADMIN_ADDRESS"] + "/internal/postfix/"
    # TODO: Remove verbosity setting from Podop?
    run_server(0, "postfix", "/tmp/podop.socket", [
		("transport", "url", url + "transport/§"),
		("alias", "url", url + "alias/§"),
		("domain", "url", url + "domain/§"),
        ("mailbox", "url", url + "mailbox/§"),
        ("recipientmap", "url", url + "recipient/map/§"),
        ("sendermap", "url", url + "sender/map/§"),
        ("senderaccess", "url", url + "sender/access/§"),
        ("senderlogin", "url", url + "sender/login/§"),
        ("senderrate", "url", url + "sender/rate/§")
    ])

def is_valid_postconf_line(line):
    return not line.startswith("#") \
            and not line == ''

# Actual startup script
os.environ["FRONT_ADDRESS"] = system.get_host_address_from_environment("FRONT", "front")
os.environ["ADMIN_ADDRESS"] = system.get_host_address_from_environment("ADMIN", "admin")
os.environ["ANTISPAM_MILTER_ADDRESS"] = system.get_host_address_from_environment("ANTISPAM_MILTER", "antispam:11332")
os.environ["LMTP_ADDRESS"] = system.get_host_address_from_environment("LMTP", "imap:2525")
os.environ["OUTCLEAN"] = os.environ["HOSTNAMES"].split(",")[0]
try:
    _to_lookup = os.environ["OUTCLEAN"]
    # Ensure we lookup a FQDN: @see #1884
    if not _to_lookup.endswith('.'):
        _to_lookup += '.'
    os.environ["OUTCLEAN_ADDRESS"] = system.resolve_hostname(_to_lookup)
except:
    os.environ["OUTCLEAN_ADDRESS"] = "10.10.10.10"

for postfix_file in glob.glob("/conf/*.cf"):
    conf.jinja(postfix_file, os.environ, os.path.join("/etc/postfix", os.path.basename(postfix_file)))

if os.path.exists("/overrides/postfix.cf"):
    for line in open("/overrides/postfix.cf").read().strip().split("\n"):
        if is_valid_postconf_line(line):
            os.system('postconf -e "{}"'.format(line))

if os.path.exists("/overrides/postfix.master"):
    for line in open("/overrides/postfix.master").read().strip().split("\n"):
        if is_valid_postconf_line(line):
            os.system('postconf -Me "{}"'.format(line))

for map_file in glob.glob("/overrides/*.map"):
    destination = os.path.join("/etc/postfix", os.path.basename(map_file))
    shutil.copyfile(map_file, destination)
    os.system("postmap {}".format(destination))
    os.remove(destination)

if not os.path.exists("/etc/postfix/tls_policy.map.db"):
    with open("/etc/postfix/tls_policy.map", "w") as f:
        for domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'aol.com', 'outlook.com', 'comcast.net', 'icloud.com', 'msn.com', 'hotmail.co.uk', 'live.com', 'yahoo.co.in', 'me.com', 'mail.ru', 'cox.net', 'yahoo.co.uk', 'verizon.net', 'ymail.com', 'hotmail.it', 'kw.com', 'yahoo.com.tw', 'mac.com', 'live.se', 'live.nl', 'yahoo.com.br', 'googlemail.com', 'libero.it', 'web.de', 'allstate.com', 'btinternet.com', 'online.no', 'yahoo.com.au', 'live.dk', 'earthlink.net', 'yahoo.fr', 'yahoo.it', 'gmx.de', 'hotmail.fr', 'shawinc.com', 'yahoo.de', 'moe.edu.sg', 'naver.com', 'bigpond.com', 'statefarm.com', 'remax.net', 'rocketmail.com', 'live.no', 'yahoo.ca', 'bigpond.net.au', 'hotmail.se', 'gmx.at', 'live.co.uk', 'mail.com', 'yahoo.in', 'yandex.ru', 'qq.com', 'charter.net', 'indeedemail.com', 'alice.it', 'hotmail.de', 'bluewin.ch', 'optonline.net', 'wp.pl', 'yahoo.es', 'hotmail.no', 'pindotmedia.com', 'orange.fr', 'live.it', 'yahoo.co.id', 'yahoo.no', 'hotmail.es', 'morganstanley.com', 'wellsfargo.com', 'wanadoo.fr', 'facebook.com', 'yahoo.se', 'fema.dhs.gov', 'rogers.com', 'yahoo.com.hk', 'live.com.au', 'nic.in', 'nab.com.au', 'ubs.com', 'shaw.ca', 'umich.edu', 'westpac.com.au', 'yahoo.com.mx', 'yahoo.com.sg', 'farmersagent.com', 'yahoo.dk', 'dhs.gov']:
            f.write(f'{domain}\tsecure\n')
    os.system("postmap /etc/postfix/tls_policy.map")

if "RELAYUSER" in os.environ:
    path = "/etc/postfix/sasl_passwd"
    conf.jinja("/conf/sasl_passwd", os.environ, path)
    os.system("postmap {}".format(path))

# Run Podop and Postfix
multiprocessing.Process(target=start_podop).start()
os.system("/usr/libexec/postfix/post-install meta_directory=/etc/postfix create-missing")
# Before starting postfix, we need to check permissions on /queue
# in the event that postfix,postdrop id have changed
os.system("postfix set-permissions")
os.system("postfix start-fg")
