#!/bin/sh

# Prepare the databases
sa-update

# Update the AV database
freshclam

# Actually run Amavis
rm -f /var/run/rsyslogd.pid
/usr/sbin/clamd
/usr/sbin/amavisd
rsyslogd -n
