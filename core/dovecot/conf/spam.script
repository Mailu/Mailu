#!/bin/bash
RSPAMD_HOST="$(getent hosts {{ ANTISPAM_ADDRESS }}|cut -d\  -f1):11334"
if [[ $? -ne 0 ]]
then
	echo "Failed to lookup {{ ANTISPAM_ADDRESS }}" >&2
	exit 1
fi


tee >(rspamc -t 3 -h $RSPAMD_HOST -P mailu learn_spam /dev/stdin||true) \
       >(rspamc -t 3 -h $RSPAMD_HOST -P mailu -f 13 fuzzy_del /dev/stdin||true) \
       >(rspamc -t 3 -h $RSPAMD_HOST -P mailu -f 11 fuzzy_add /dev/stdin||true) > /dev/null

wait
