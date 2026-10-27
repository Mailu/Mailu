#!/bin/sh
set -eu

control_password=$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')
umask 077

cat >/tmp/mailu-supervisord.conf <<EOF
[supervisord]
user=root
nodaemon=true
logfile=/dev/stdout
logfile_maxbytes=0
pidfile=/tmp/mailu-supervisord.pid
childlogdir=/tmp
loglevel=info

[unix_http_server]
file=/tmp/mailu-supervisor.sock
chmod=0700
username=mailu-supervisorctl
password=$control_password

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[supervisorctl]
serverurl=unix:///tmp/mailu-supervisor.sock
username=mailu-supervisorctl
password=$control_password

[program:nginx]
command=/usr/sbin/nginx -g "daemon off;"
autostart=true
autorestart=true
startsecs=1
startretries=3
stopsignal=TERM
stopwaitsecs=30
stopasgroup=true
killasgroup=true
redirect_stderr=true
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
EOF

cat >/tmp/mailu-supervisorctl.conf <<EOF
[supervisorctl]
serverurl=unix:///tmp/mailu-supervisor.sock
username=mailu-supervisorctl
password=$control_password
EOF
chmod 600 /tmp/mailu-supervisorctl.conf

exec /usr/bin/env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin TZ=Etc/UTC \
    /usr/bin/supervisord -n -c /tmp/mailu-supervisord.conf
