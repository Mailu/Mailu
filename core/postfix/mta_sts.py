#!/usr/bin/env python3

import os

from socrate import system
from postfix_mta_sts_resolver import daemon

os.chmod("/root/", 0o755)  # read access to /root/.netrc required
system.drop_privs_to("postfix")
daemon.main()
