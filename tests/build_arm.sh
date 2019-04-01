#!/bin/bash -x

ALPINE_VER="3.8"
DISTRO="balenalib/rpi-alpine:$ALPINE_VER"
# Used for Radicale
EDGE_DISTRO="balenalib/rpi-alpine:edge"
# Used for webmails
PHP="arm32v7/php:7.2-apache"

# NOTE: Might not be needed since using multiarch/qemu
QEMU="$(which qemu-arm-static)"
cp $QEMU ../webmails/rainloop/
cp $QEMU ../webmails/roundcube/

# use qemu-*-static from docker container
docker run --rm --privileged multiarch/qemu-user-static:register 
docker-compose -f build.yml build --build-arg DISTRO=$DISTRO --build-arg PHP_DISTRO=$PHP --build-arg EDGE_DISTRO=$EDGE_DISTRO --parallel $@
