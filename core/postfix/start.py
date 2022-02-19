#!/usr/bin/python3

import os
import glob
import shutil
import multiprocessing
import logging as log
import sys

from podop import run_server
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
        ("dane", "url", url + "dane/§"),
        ("domain", "url", url + "domain/§"),
        ("mailbox", "url", url + "mailbox/§"),
        ("recipientmap", "url", url + "recipient/map/§"),
        ("sendermap", "url", url + "sender/map/§"),
        ("senderaccess", "url", url + "sender/access/§"),
        ("senderlogin", "url", url + "sender/login/§"),
        ("senderrate", "url", url + "sender/rate/§")
    ])

def start_mta_sts_daemon():
    os.chmod("/root/", 0o755) # read access to /root/.netrc required
    os.setuid(getpwnam('postfix').pw_uid)
    from postfix_mta_sts_resolver import daemon
    daemon.main()

def is_valid_postconf_line(line):
    return not line.startswith("#") \
            and not line == ''

# Actual startup script
os.environ['DEFER_ON_TLS_ERROR'] = os.environ['DEFER_ON_TLS_ERROR'] if 'DEFER_ON_TLS_ERROR' in os.environ else 'True'
os.environ["FRONT_ADDRESS"] = system.get_host_address_from_environment("FRONT", "front")
os.environ["ADMIN_ADDRESS"] = system.get_host_address_from_environment("ADMIN", "admin")
os.environ["ANTISPAM_MILTER_ADDRESS"] = system.get_host_address_from_environment("ANTISPAM_MILTER", "antispam:11332")
os.environ["LMTP_ADDRESS"] = system.get_host_address_from_environment("LMTP", "imap:2525")
os.environ["POSTFIX_LOG_SYSLOG"] = os.environ.get("POSTFIX_LOG_SYSLOG","local")
os.environ["POSTFIX_LOG_FILE"] = os.environ.get("POSTFIX_LOG_FILE", "")

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

if os.path.exists("/overrides/mta-sts-daemon.yml"):
    shutil.copyfile("/overrides/mta-sts-daemon.yml", "/etc/mta-sts-daemon.yml")
else:
    conf.jinja("/conf/mta-sts-daemon.yml", os.environ, "/etc/mta-sts-daemon.yml")

for policy in ['tls_policy', 'transport']:
    if not os.path.exists(f'/etc/postfix/{policy}.map.lmdb'):
        open(f'/etc/postfix/{policy}.map', 'a').close()
        os.system(f'postmap /etc/postfix/{policy}.map')

if "RELAYUSER" in os.environ:
    path = "/etc/postfix/sasl_passwd"
    conf.jinja("/conf/sasl_passwd", os.environ, path)
    os.system("postmap {}".format(path))

# Configure and start local rsyslog server
conf.jinja("/conf/rsyslog.conf", os.environ, "/etc/rsyslog.conf")
os.system("/usr/sbin/rsyslogd -niNONE &")
# Configure logrotate and start crond
if os.environ["POSTFIX_LOG_FILE"] != "":
    conf.jinja("/conf/logrotate.conf", os.environ, "/etc/logrotate.d/postfix.conf")
    os.system("/usr/sbin/crond")
    if os.path.exists("/overrides/logrotate.conf"):
        shutil.copyfile("/overrides/logrotate.conf", "/etc/logrotate.d/postfix.conf")

# Run Podop and Postfix
multiprocessing.Process(target=start_podop).start()
multiprocessing.Process(target=start_mta_sts_daemon).start()
os.system("/usr/libexec/postfix/post-install meta_directory=/etc/postfix create-missing")
# Before starting postfix, we need to check permissions on /queue
# in the event that postfix,postdrop id have changed
os.system("postfix set-permissions")
os.system("postfix start-fg")
