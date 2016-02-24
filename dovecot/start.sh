#!/bin/sh

# Fix permissions
chown -R mail:mail /mail
chown -R mail:mail /var/lib/dovecot

# Run dovecot
exec /usr/sbin/dovecot -c /etc/dovecot/dovecot.conf -F
