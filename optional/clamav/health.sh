#!/bin/sh

if [ "$(echo PING | nc localhost 3310)" = "PONG" ]; then
	echo "ping successful"
else
	echo "ping failed"
	exit 1
fi
