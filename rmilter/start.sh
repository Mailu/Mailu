#!/bin/bash

export WHITELIST=$(echo "$RELAYNETS" | sed 's/ /,/g')

# Substitute configuration
for VARIABLE in `env | cut -f1 -d=`; do
  sed -i "s={{ $VARIABLE }}=${!VARIABLE}=g" /etc/rmilter.conf
done

rm -f /var/run/rsyslogd.pid
rmilter -c /etc/rmilter.conf
rsyslogd -n
