#!/bin/sh

# Prepare the databases
sa-update

# Update the AV database
freshclam

# Actually run Amavis
/usr/sbin/clamd
/usr/sbin/amavisd
rsyslogd -n
