#!/bin/bash -x

export DISTRO="hypriot/rpi-alpine"
docker-compose -f build.yml build --build-arg DISTRO=$DISTRO # --parallel
