#!/bin/bash

# Skip deploy for staging branch
[ "$TRAVIS_BRANCH" = "staging" ] && exit 0

# Retag in case of `bors try`
if [ "$TRAVIS_BRANCH" = "testing" ]; then
    export DOCKER_ORG=$DOCKER_ORG_TESTS
    # Commit message is like "Try #99".
    # This sets the version tag to "pr-99"
    export MAILU_VERSION="pr-${TRAVIS_COMMIT_MESSAGE//[!0-9]/}"
    docker-compose -f tests/build.yml build
fi

docker login -u $DOCKER_UN -p $DOCKER_PW
docker-compose -f tests/build.yml push
