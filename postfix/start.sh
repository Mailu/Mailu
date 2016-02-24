#!/bin/sh

/usr/lib/postfix/master &
rsyslogd -n
