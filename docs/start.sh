#!/bin/sh
set -eu

control_password=$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')
umask 077

cat >/etc/supervisord.conf <<EOF
[supervisord]
user=root
pidfile=/run/mailu-supervisor/supervisord.pid
nodaemon=true
logfile=/dev/stdout
logfile_maxbytes=0
childlogdir=/tmp
loglevel=info

[unix_http_server]
file=/run/mailu-supervisor/supervisor.sock
chmod=0700
username=mailu-supervisorctl
password=$control_password

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[supervisorctl]
serverurl=unix:///run/mailu-supervisor/supervisor.sock
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

chmod 600 /etc/supervisord.conf
mkdir -p /run/mailu-supervisor

exec /usr/bin/env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin TZ=Etc/UTC \
    /usr/bin/supervisord -n -c /etc/supervisord.conf
