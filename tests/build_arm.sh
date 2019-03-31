#!/bin/bash -x

DISTRO="balenalib/rpi-alpine:3.8"
PHP="arm32v7/php:7.2-apache"
QEMU="$(which qemu-arm-static)"
cp $QEMU ../webmails/rainloop/
cp $QEMU ../webmails/roundcube/

docker-compose -f build.yml build --build-arg DISTRO=$DISTRO --build-arg PHP_DISTRO=$PHP --parallel $@
