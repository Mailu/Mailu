#!/bin/bash

[[ `curl -I -so /dev/null -w "%{http_code}" http://localhost/` -ne 200 ]] && echo "The default page of snappymail hasn't returned 200!" >>/dev/stderr && exit 1
[[ `curl -I -so /dev/null -w "%{http_code}" http://localhost/?admin` -ne 403 ]] && echo "The admin of snappymail is not disabled!" >>/dev/stderr && exit 1
