#!/bin/bash

# Skip deploy for staging branch
[ "$TRAVIS_BRANCH" = "staging" ] && exit 0

docker login -u $DOCKER_UN -p $DOCKER_PW
docker-compose -f tests/build.yml push
