#!/bin/bash

# Substitute configuration
for VARIABLE in `env | cut -f1 -d=`; do
  sed -i "s={{ $VARIABLE }}=${!VARIABLE}=g" /conf/*.toml
done

# Select the proper configuration
cp /conf/$TLS_FLAVOR.toml /conf/traefik.toml

exec traefik -c /conf/traefik.toml

