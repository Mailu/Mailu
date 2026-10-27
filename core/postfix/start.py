#!/usr/bin/env python3

import os
import glob
import shutil
import sys

from socrate import system, conf, supervisor
from chroot import prepare_postfix_chroot

log_filters = [
    rb'(dis)?connect from localhost\[(\:\:1|127\.0\.0\.1)\]( quit=1 commands=1)?$',
    rb'haproxy read\: short protocol header\: QUIT$',
    rb'discarding EHLO keywords\: PIPELINING$',
    rb'the Postfix mail system is running: PID: \d+$',
]
env = system.set_env()

def is_valid_postconf_line(line):
    return not line.startswith("#") \
            and not line == ''

# Actual startup script

# Postfix requires IPv6 addresses to be wrapped in square brackets
if 'RELAYNETS' in os.environ:
    relaynets = []
    for net in os.environ["RELAYNETS"].split(','):
        addr, sep, prefix = net.strip().partition('/')
        if ':' in addr and not addr.startswith('['):
            addr = f'[{addr}]'
        relaynets.append(addr + sep + prefix)
    os.environ["RELAYNETS"] = ','.join(relaynets)

context = dict(os.environ, DEFER_ON_TLS_ERROR=env.get('DEFER_ON_TLS_ERROR', True))

for postfix_file in glob.glob("/conf/*.cf"):
    conf.jinja(postfix_file, context, os.path.join("/etc/postfix", os.path.basename(postfix_file)))

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
    conf.jinja("/conf/mta-sts-daemon.yml", context, "/etc/mta-sts-daemon.yml")

for policy in ['tls_policy', 'transport']:
    if not os.path.exists(f'/etc/postfix/{policy}.map.lmdb'):
        open(f'/etc/postfix/{policy}.map', 'a').close()
        os.system(f'postmap /etc/postfix/{policy}.map')

sasl_passwd = None
if "RELAYUSER" in os.environ:
    path = "/etc/postfix/sasl_passwd"
    conf.jinja("/conf/sasl_passwd", context, path)
    sasl_passwd = path

supervisor.clean_environment()

if sasl_passwd:
    os.system("postmap {}".format(sasl_passwd))

# Configure logrotate
if os.environ.get('POSTFIX_LOG_FILE'):
    conf.jinja("/conf/logrotate.conf", context, "/etc/logrotate.d/postfix.conf")
    if os.path.exists("/overrides/logrotate.conf"):
        shutil.copyfile("/overrides/logrotate.conf", "/etc/logrotate.d/postfix.conf")

# Prepare Postfix before handing its long-running processes to supervisord.
os.system("/usr/libexec/postfix/post-install meta_directory=/etc/postfix create-missing")
# Before starting postfix, we need to check permissions on /queue
# in the event that postfix,postdrop id have changed
os.system("postfix set-permissions")
prepare_postfix_chroot()

programs = [
    {"name": "podop", "command": ["python3", "-m", "podop.run_server", "postfix"], "priority": 10},
    {"name": "postfix", "command": ["postfix", "start-fg"], "log_filters": log_filters, "priority": 20},
]
if os.environ.get('POSTFIX_LOG_FILE'):
    programs.append({"name": "cron", "command": ["/usr/sbin/crond", "-f", "-l", "2", "-L", "/proc/1/fd/1"]})
if os.path.exists("/etc/mta-sts-daemon.yml"):
    os.chmod("/root/", 0o755)  # read access to /root/.netrc required
    programs.append({"name": "mta-sts", "command": ["python3", "/mta_sts.py"]})
supervisor.start(programs)
