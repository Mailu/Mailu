#!/bin/sh

rm -f /var/run/rsyslogd.pid
rmilter -c /etc/rmilter.conf
rsyslogd -n
