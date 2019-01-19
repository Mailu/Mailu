#!/bin/bash

function dump() {
    echo "$(date) Dumping certificates"

<<<<<<< HEAD
    traefik-certs-dumper file --version ${TRAEFIK_VERSION:-v1} --crt-name "cert" --crt-ext ".pem" --key-name "key" --key-ext ".pem" --domain-subdir --dest /tmp/work --source /traefik/acme.json > /dev/null

    if [[ -f "/tmp/work/${DOMAIN}/cert.pem" && -f "/tmp/work/${DOMAIN}/key.pem" && -f /output/cert.pem && -f /output/key.pem ]] && \
	diff -q "/tmp/work/${DOMAIN}/cert.pem" /output/cert.pem >/dev/null && \
	diff -q "/tmp/work/${DOMAIN}/key.pem" /output/key.pem >/dev/null ; \
    then
	echo "$(date) Certificate and key still up to date, doing nothing"
    else
	echo "$(date) Certificate or key differ, updating"
	mv "/tmp/work/${DOMAIN}"/*.pem /output/
    fi
=======
    # private-keys are rsa, we need pem though
    for key_file in $(ls /tmp/work/private/*); do
        pem_file=$(echo $key_file | sed 's/private/pem/g' | sed 's/.key/-private.pem/g')
        openssl rsa -in $key_file -text > $pem_file
    done

    echo "$(date) Copying certificates"
    cp -v /tmp/work/pem/${DOMAIN}-private.pem /output/key.pem
    # the .crt is a chained-pem, as common for letsencrypt
    cp -v /tmp/work/certs/${DOMAIN}.crt /output/cert.pem
>>>>>>> 2c5f9771 (Make certdumper output fullchain-pems)
}

mkdir -p /tmp/work
dump

while true; do
    inotifywait -qq -e modify /traefik/acme.json
    dump
done
