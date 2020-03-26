#!/bin/bash

# Retag in case of `bors try`
if [ "$TRAVIS_BRANCH" = "testing" ]; then
    export DOCKER_ORG="mailutest"
    # Commit message is like "Try #99".
    # This sets the version tag to "pr-99"
    export MAILU_VERSION="pr-${TRAVIS_COMMIT_MESSAGE//[!0-9]/}"
fi
