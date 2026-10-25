#!/bin/sh
set -eu

domain=${DOMAIN:?DOMAIN is required}
traefik_version=${TRAEFIK_VERSION:-v1}
case "$domain:$traefik_version" in
    *[!A-Za-z0-9._:-]*) echo "DOMAIN or TRAEFIK_VERSION contains unsupported characters" >&2; exit 1 ;;
esac

umask 077
exec /usr/bin/env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin TZ=Etc/UTC LANG=C.UTF-8 \
    DOMAIN="$domain" TRAEFIK_VERSION="$traefik_version" /run.sh
