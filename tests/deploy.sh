#!/bin/bash

# Re-tag images fir PR testing
if [ $TRAVIS_PULL_REQUEST != false ] then;
    export MAILU_VERSION="${TRAVIS_BRANCH}-${TRAVIS_PULL_REQUEST}"
    export DOCKER_ORG="mailutest"
    docker-compose -f tests/build.yml build
fi

if [ -n $DOCKER_UN ] && [ -n $DOCKER_PW ]; then
    docker login -u $DOCKER_UN -p $DOCKER_PW
    docker-compose -f tests/build.yml push
fi
