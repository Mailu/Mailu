#!/bin/bash

IP="$(docker inspect webmail_webmail_1|jq -r '.[0].NetworkSettings.Networks.webmail_default.IPAddress')"

MAIN_RETURN_CODE=$(curl -I -so /dev/null -w "%{http_code}" http://$IP/)
[[ $MAIN_RETURN_CODE -ne 200 && $MAIN_RETURN_CODE -ne 302 ]] && echo "The default page of snappymail hasn't returned 200 but $MAIN_RETURN_CODE!" >>/dev/stderr && exit 1
[[ $(curl -I -so /dev/null -w "%{http_code}" http://$IP/?admin) -ne 403 ]] && echo "The admin of snappymail is not disabled!" >>/dev/stderr && exit 1
echo "Everything OK" >/dev/stderr

exit 0
