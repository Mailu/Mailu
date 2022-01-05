#!/usr/bin/python3

import os
import logging as log
import sys

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO"))

os.system("flask mailu advertise")
os.system("flask db upgrade")

account = os.environ.get("INITIAL_ADMIN_ACCOUNT")
domain = os.environ.get("INITIAL_ADMIN_DOMAIN")
password = os.environ.get("INITIAL_ADMIN_PW")

if account is not None and domain is not None and password is not None:
    mode = os.environ.get("INITIAL_ADMIN_MODE", default="ifmissing")
    log.info("Creating initial admin accout %s@%s with mode %s",account,domain,mode)
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
    resolver.use_edns(0, 0, 1232)
    resolver.flags = dns.flags.AD | dns.flags.RD
    nameservers = resolver.nameservers
    for ns in nameservers:
        resolver.nameservers=[ns]
        error = True
        while error:
            try:
                result = resolver.query('example.org', dns.rdatatype.A, dns.rdataclass.IN, lifetime=10)
                if not result.response.flags & dns.flags.AD:
                    log.critical("Your DNS resolver at %s isn't doing DNSSEC validation; Please install unbound.", ns)
                else:
                    error = False
                    continue
            except Exception as e:
                log.critical("Your DNS resolver at %s is not working (%s). Please install unbound.", ns, e);
            time.sleep(5)

test_DNS()

start_command="".join([
    "gunicorn --threads ", str(os.cpu_count()),
    " -b :80 ",
    "--access-logfile - " if (log.root.level<=log.INFO) else "",
    "--error-logfile - ",
    "--preload ",
    "'mailu:create_app()'"])

os.system(start_command)
