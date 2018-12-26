#!/bin/bash

function dump() {
    echo "$(date) Dumping certificates"
    bash dumpcerts.sh /traefik/acme.json /tmp/work/

    for crt_file in $(ls /tmp/work/certs/*); do
        pem_file=$(echo $crt_file | sed 's/certs/pem/g' | sed 's/.crt/-public.pem/g')
        echo "openssl x509 -inform PEM -in $crt_file > $pem_file"
        openssl x509 -inform PEM -in $crt_file > $pem_file
    done
    for key_file in $(ls /tmp/work/private/*); do
        pem_file=$(echo $key_file | sed 's/private/pem/g' | sed 's/.key/-private.pem/g')
        echo "openssl rsa -in $key_file -text > $pem_file"
        openssl rsa -in $key_file -text > $pem_file
    done

    echo "$(date) Copying certificates"
    cp -v /tmp/work/pem/${DOMAIN}-private.pem /output/key.pem
    cp -v /tmp/work/pem/${DOMAIN}-public.pem /output/cert.pem
}

mkdir -p /tmp/work/pem /tmp/work/certs
# run once on start to make sure we have any old certs
dump

while true; do
    inotifywait -e modify /traefik/acme.json && \
        dump
done
