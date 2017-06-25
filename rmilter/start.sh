#!/bin/sh

rm -f /var/run/rsyslogd.pid
if [ "$ANTIVIRUS" == "clamav" ];
then
	echo "# .try_include /etc/rmilter-clamav.conf" >>  /etc/rmilter.conf
fi
rmilter -c /etc/rmilter.conf
rsyslogd -n
