#!/bin/bash

IP="$(docker inspect webmail_webmail_1|jq -r '.[0].NetworkSettings.Networks.webmail_default.IPAddress')"

echo "webmail is on $IP" >/dev/stderr
wget -S -O - "http://$IP/" &>/dev/stderr
docker inspect webmail_webmail_1 &>/dev/stderr

[[ $(curl -I -so /dev/null -w "%{http_code}" http://$IP/) -ne 200 ]] && echo "The default page of snappymail hasn't returned 200!" >>/dev/stderr && exit 1
[[ $(curl -I -so /dev/null -w "%{http_code}" http://$IP/?admin) -ne 403 ]] && echo "The admin of snappymail is not disabled!" >>/dev/stderr && exit 1
