#!/usr/bin/env python3

import os
import logging as log
import sys
from socrate import system

os.system("chown mailu:mailu -R /dkim")
os.system("find /data | grep -v /fetchmail | xargs -n1 chown mailu:mailu")
system.drop_privs_to('mailu')

system.set_env(['SECRET'])

os.system("flask mailu advertise")
os.system("flask db upgrade")

account = os.environ.get("INITIAL_ADMIN_ACCOUNT")
domain = os.environ.get("INITIAL_ADMIN_DOMAIN")
password = os.environ.get("INITIAL_ADMIN_PW")

if account is not None and domain is not None and password is not None:
    mode = os.environ.get("INITIAL_ADMIN_MODE", default="ifmissing")
    log.info("Creating initial admin account %s@%s with mode %s", account, domain, mode)
    os.system("flask mailu admin %s %s '%s' --mode %s" % (account, domain, password, mode))

def test_DNS():
    import dns.resolver
    import dns.exception
    import dns.flags
    import dns.rdtypes
    import dns.rdatatype
    import dns.rdataclass
    import time
    # DNS stub configured to do DNSSEC enabled queries
    resolver = dns.resolver.Resolver()
    resolver.use_edns(0, dns.flags.DO, 1232)
    resolver.flags = dns.flags.AD | dns.flags.RD
    nameservers = resolver.nameservers
    for ns in nameservers:
        resolver.nameservers=[ns]
        while True:
            try:
                result = resolver.resolve('example.org', dns.rdatatype.A, dns.rdataclass.IN, lifetime=10)
            except Exception as e:
                log.critical("Your DNS resolver at %s is not working (%s). Please see https://mailu.io/master/faq.html#the-admin-container-won-t-start-and-its-log-says-critical-your-dns-resolver-isn-t-doing-dnssec-validation", ns, e)
            else:
                if result.response.flags & dns.flags.AD:
                    break
                log.critical("Your DNS resolver at %s isn't doing DNSSEC validation; Please see https://mailu.io/master/faq.html#the-admin-container-won-t-start-and-its-log-says-critical-your-dns-resolver-isn-t-doing-dnssec-validation.", ns)
            time.sleep(5)

test_DNS()

cmdline = [
    "gunicorn",
    "--threads", f"{os.cpu_count()}",
    # If SUBNET6 is defined, gunicorn must listen on IPv6 as well as IPv4
    "-b", f"{'[::]' if os.environ.get('SUBNET6') else '0.0.0.0'}:8080",
    "--logger-class mailu.Logger",
    "--worker-tmp-dir /dev/shm",
	"--error-logfile", "-",
	"--preload"
]

# logging
if log.root.level <= log.INFO:
	cmdline.extend(["--access-logfile", "-"])

cmdline.append("'mailu:create_app()'")

os.system(" ".join(cmdline))
