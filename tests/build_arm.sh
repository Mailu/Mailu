#!/bin/bash -x

ALPINE_VER="3.14"
DISTRO="balenalib/rpi-alpine:$ALPINE_VER"
# Used for webmails
QEMU="arm"
ARCH="arm32v7/"

# use qemu-*-static from docker container
docker run --rm --privileged multiarch/qemu-user-static:register 
docker-compose -f build.yml build \
  --build-arg DISTRO=$DISTRO \
  --build-arg ARCH=$ARCH \
  --build-arg QEMU=$QEMU \
  --parallel $@
