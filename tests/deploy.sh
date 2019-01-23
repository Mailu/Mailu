#!/bin/bash

if [ -n $DOCKER_UN ] && [ -n $DOCKER_PW ]; then
    docker login -u $DOCKER_UN -p $DOCKER_PW
    docker-compose -f tests/build.yml push
fi
