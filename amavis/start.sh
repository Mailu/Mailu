#!/bin/sh

# Prepare the databases
sa-update

# Actually run Amavis
/usr/sbin/amavisd
rsyslogd -n
