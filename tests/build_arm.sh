#!/bin/bash -x

ALPINE_VER="3.8"
DISTRO="balenalib/rpi-alpine:$ALPINE_VER"
EDGE_DISTRO="balenalib/rpi-alpine:edge"
PHP="arm32v7/php:7.2-apache"
QEMU="$(which qemu-arm-static)"
cp $QEMU ../webmails/rainloop/
cp $QEMU ../webmails/roundcube/

docker-compose -f build.yml build --build-arg DISTRO=$DISTRO --build-arg PHP_DISTRO=$PHP --build-arg EDGE_DISTRO=$EDGE_DISTRO --parallel $@
