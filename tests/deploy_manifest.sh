#!/bin/bash

# Skip deploy for staging branch
[ "$TRAVIS_BRANCH" = "staging" ] && exit 0

# Retag in case of `bors try`
if [ "$TRAVIS_BRANCH" = "testing" ]; then
    export DOCKER_ORG="mailutest"
    # Commit message is like "Try #99".
    # This sets the version tag to "pr-99"
    export MAILU_VERSION="pr-${TRAVIS_COMMIT_MESSAGE//[!0-9]/}"
fi

docker login -u $DOCKER_UN -p $DOCKER_PW

# List of all Mailu services:
MailuSrvList="nginx unbound dovecot postfix rspamd clamav radicale traefik-certdumper admin postgresql roundcube rainloop fetchmail none docs setup"
# Iterate for each Mailu service. Retag images (removing -ci), and create multiarch manifest  
for MailuSrv in $MailuSrvList; do
    echo "Retagging ${MailuSrv} and pushing it, for amd64 and arm64"
    docker pull ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}${MAILU_CI}:amd64-${MAILU_VERSION:-local}
    docker tag  ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}${MAILU_CI}:amd64-${MAILU_VERSION:-local} \
                ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}:amd64-${MAILU_VERSION:-local}
    docker push ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}:amd64-${MAILU_VERSION:-local}
    docker pull ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}${MAILU_CI}:arm64-${MAILU_VERSION:-local}
    docker tag  ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}${MAILU_CI}:arm64-${MAILU_VERSION:-local} \
                ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}:arm64-${MAILU_VERSION:-local}
    docker push ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}:arm64-${MAILU_VERSION:-local}
    echo "Creating manifest for ${MailuSrv}"
    DOCKER_CLI_EXPERIMENTAL=enabled  docker manifest create \
       ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}:${MAILU_VERSION:-local} \
       --amend  ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}:amd64-${MAILU_VERSION:-local} \
       --amend  ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}:arm64-${MAILU_VERSION:-local}	
    DOCKER_CLI_EXPERIMENTAL=enabled  docker manifest annotate \
       ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}:${MAILU_VERSION:-local} \
       ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}:arm64-${MAILU_VERSION:-local} --os linux --arch arm64 --variant v8
    DOCKER_CLI_EXPERIMENTAL=enabled  docker manifest push \
       ${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}${MailuSrv}:${MAILU_VERSION:-local}
done
