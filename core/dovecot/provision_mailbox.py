#!/usr/bin/env python3
"""Create a protected mailbox home for the account selected by global Sieve."""
import fcntl
import json
import os
import sys
from urllib.parse import quote
from urllib.request import urlopen
from socrate.mailbox import provision




def main():
    if len(sys.argv) != 3:
        raise ValueError('Expected admin address and mailbox email')
    admin, email = sys.argv[1:]
    url = f'http://{admin}:8080/internal/dovecot/userdb/{quote(email, safe="")}'
    with urlopen(url, timeout=5) as response:
        payload = response.read(65537)
    if len(payload) > 65536:
        raise ValueError('Userdb response too large')
    fields = json.loads(payload)
    if fields.get('email', '').casefold() != email.casefold():
        raise ValueError('Userdb returned a different account')
    # Serialize creation so a concurrent delivery never observes a freshly
    # created home before ownership has been assigned.
    lock = os.open('/run/mailu-provision.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        provision(fields)
    finally:
        os.close(lock)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Mailbox provisioning failed: {error}', file=sys.stderr)
        sys.exit(1)
