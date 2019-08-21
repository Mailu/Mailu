#!/bin/bash -x

ALPINE_VER="3.10"
DISTRO="balenalib/rpi-alpine:$ALPINE_VER"
# Used for webmails
PHP="arm32v7/php:7.3-apache"

# use qemu-*-static from docker container
docker run --rm --privileged multiarch/qemu-user-static:register 
docker-compose -f build.yml build \
  --build-arg DISTRO=$DISTRO \
  --build-arg PHP_DISTRO=$PHP \
  --parallel $@
