#!/bin/bash

# Substitute configuration
for VARIABLE in `env | cut -f1 -d=`; do
  sed -i "s={{ $VARIABLE }}=${!VARIABLE}=g" /etc/postfix/*.cf
done

# Override Postfix main configuration
if [ -f /overrides/postfix.cf ]; then
  while read line; do
    postconf -e "$line"
  done < /overrides/postfix.cf
  echo "Loaded '/overrides/postfix.cf'"
else
  echo "No extra postfix settings loaded because optional '/overrides/postfix.cf' not provided."
fi

# Override Postfix master configuration
if [ -f /overrides/master.cf ]; then
  while read line; do
    postconf -M "$line"
  done < /overrides/master.cf
  echo "Loaded '/overrides/master.cf'"
else
  echo "No extra postfix settings loaded because optional '/overrides/master.cf' not provided."
fi

# Include table-map files
if ls -A /overrides/*.map 1> /dev/null 2>&1; then
  cp /overrides/*.map /etc/postfix/
  postmap /etc/postfix/*.map
  rm /etc/postfix/*.map
  chown root:root /etc/postfix/*.db
  chmod 0600 /etc/postfix/*.db
  echo "Loaded 'map files'"
else
  echo "No extra map files loaded because optional '/overrides/*.map' not provided."
fi

# Actually run Postfix
rm -f /var/run/rsyslogd.pid
chown -R postfix: /queue
/usr/lib/postfix/post-install meta_directory=/etc/postfix create-missing
/usr/lib/postfix/master &
exec rsyslogd -n
