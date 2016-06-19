#!/bin/sh

rspamd -i
tail -f /var/log/rspamd/rspamd.log
