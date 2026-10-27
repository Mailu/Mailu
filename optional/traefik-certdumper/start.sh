#!/bin/sh
set -eu

domain=${DOMAIN:?DOMAIN is required}
traefik_version=${TRAEFIK_VERSION:-v1}
case "$domain:$traefik_version" in
    *[!A-Za-z0-9._:-]*) echo "DOMAIN or TRAEFIK_VERSION contains unsupported characters" >&2; exit 1 ;;
esac

umask 077
control_password=$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')

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

[program:certdumper]
command=/run.sh
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
environment=DOMAIN="$domain",TRAEFIK_VERSION="$traefik_version"
EOF

chmod 600 /etc/supervisord.conf
mkdir -p /run/mailu-supervisor

exec /usr/bin/env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin TZ=Etc/UTC LANG=C.UTF-8 \
    /usr/bin/supervisord -n -c /etc/supervisord.conf
