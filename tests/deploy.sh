#!/bin/bash

# Re-tag images for PR testing
if [ $TRAVIS_PULL_REQUEST != false ]; then
    export MAILU_VERSION="${TRAVIS_BRANCH}-${TRAVIS_PULL_REQUEST}"
    export DOCKER_ORG="mailutest"
    docker-compose -f tests/build.yml build
fi


# Note that in case of a PR, the branch is the one we are merging into
if [ -n $DOCKER_UN ] && [ -n $DOCKER_PW ] && \
{ [ "$TRAVIS_BRANCH" = "master" ] || [ "$TRAVIS_BRANCH" = "1.6" ]; }; then
    docker login -u $DOCKER_UN -p $DOCKER_PW
    docker-compose -f tests/build.yml push
fi
