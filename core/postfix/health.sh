#!/bin/sh

if [ "$(echo QUIT|nc localhost 25|tail -n1|cut -f1 -d ' ')" = "221" ]; then
	echo "ping successful"
else
	echo "ping failed"
	exit 1
fi
