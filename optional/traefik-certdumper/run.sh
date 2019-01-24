#!/bin/bash

function dump() {
    echo "$(date) Dumping certificates"
    bash dumpcerts.sh /traefik/acme.json /tmp/work/ || return

    # private-keys are rsa, we need pem though
    for key_file in $(ls /tmp/work/private/*); do
        pem_file=$(echo $key_file | sed 's/private/pem/g' | sed 's/.key/-private.pem/g')
        openssl rsa -in $key_file -text > $pem_file
    done

    echo "$(date) Copying certificates"
    cp -v /tmp/work/pem/${DOMAIN}-private.pem /output/key.pem
    # the .crt is a chained-pem, as common for letsencrypt
    cp -v /tmp/work/certs/${DOMAIN}.crt /output/cert.pem
}

mkdir -p /tmp/work/pem /tmp/work/certs
# run once on start to make sure we have any old certs
dump

while true; do
    inotifywait -e modify /traefik/acme.json && \
        dump
done
