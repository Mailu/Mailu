#!/usr/bin/env python3

import os
import glob
import shutil
import multiprocessing
import sys
import re

from podop import run_server
from socrate import system, conf

system.set_env(log_filters=[
    r'(dis)?connect from localhost\[(\:\:1|127\.0\.0\.1)\]( quit=1 commands=1)?$',
    r'haproxy read\: short protocol header\: QUIT$',
    r'discarding EHLO keywords\: PIPELINING$'
    ])

os.system("flock -n /queue/pid/master.pid rm /queue/pid/master.pid")

def start_podop():
    system.drop_privs_to('postfix')
    os.makedirs('/dev/shm/postfix',mode=0o700, exist_ok=True)
    url = "http://" + os.environ["ADMIN_ADDRESS"] + ":8080/internal/postfix/"
    # TODO: Remove verbosity setting from Podop?
    run_server(0, "postfix", "/tmp/podop.socket", [
        ("transport", "url", url + "transport/§"),
        ("alias", "url", url + "alias/§"),
        ("dane", "url", url + "dane/§"),
        ("domain", "url", url + "domain/§"),
        ("mailbox", "url", url + "mailbox/§"),
        ("recipientmap", "url", url + "recipient/map/§"),
        ("sendermap", "url", url + "sender/map/§"),
        ("senderlogin", "url", url + "sender/login/§"),
        ("senderrate", "url", url + "sender/rate/§")
    ])

def start_mta_sts_daemon():
    os.chmod("/root/", 0o755) # read access to /root/.netrc required
    system.drop_privs_to('postfix')
    from postfix_mta_sts_resolver import daemon
    daemon.main()

def is_valid_postconf_line(line):
    return not line.startswith("#") \
            and not line == ''

# Actual startup script
os.environ['DEFER_ON_TLS_ERROR'] = os.environ['DEFER_ON_TLS_ERROR'] if 'DEFER_ON_TLS_ERROR' in os.environ else 'True'

# Postfix requires IPv6 addresses to be wrapped in square brackets
if 'RELAYNETS' in os.environ:
    os.environ["RELAYNETS"] = re.sub(r'([0-9a-fA-F]+:[0-9a-fA-F:]+)/', '[\\1]/', os.environ["RELAYNETS"])

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

# Configure logrotate and start crond
if os.environ.get('POSTFIX_LOG_FILE'):
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
cmd = ['postfix', 'start-fg']
system.run_process_and_forward_output(cmd)
