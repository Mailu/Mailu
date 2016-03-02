#!/bin/bash

# Substitute configuration
for VARIABLE in `env | cut -f1 -d=`; do
  sed -i "s,{{ $VARIABLE }},${!VARIABLE},g" /etc/postfix/*.cf
done

# Actually run Postfix
/usr/lib/postfix/master &
rsyslogd -n
