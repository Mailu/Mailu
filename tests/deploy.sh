#!/bin/bash

# Skip deploy for staging branch
[ "$BRANCH" = "staging" ] && exit 0

docker login -u $DOCKER_UN -p $DOCKER_PW

if [ "$BRANCH" = "testing" ]
then
  docker-compose -f tests/build.yml push
  exit 0
fi

#Deploy for main releases
#Images are built with tag PINNED_MAILU_VERSION (x.y.z).
#We are tagging them as well with MAILU_VERSION (x.y)
#After that, both tags are pushed to the docker repository.
#if [ "$PINNED_MAILU_VERSION" != "" ] && [ "$BRANCH" != "master" ]
#then
  #images=$(docker-compose -f tests/build.yml config | awk -F ':' '/image:/{ print $2 }')
  #for image in $images
  #do
  #  docker tag "${image}":"${PINNED_MAILU_ARCH_VERSION}" "${image}":${MAILU_VERSION}
  #done
#Push PINNED_MAILU_VERSION images
#  docker-compose -f tests/build.yml push
#Push MAILU_VERSION images
  #PINNED_MAILU_ARCH_VERSION=$MAILU_VERSION
  #docker-compose -f tests/build.yml push
#  exit 0
#fi

#Deploy for master. For master we only publish images with tag master
#Images are built with tag PINNED_MAILU_VERSION (commit hash).
#We are tagging them as well with MAILU_VERSION (master)
#Then we publish the images with tag master
#if [ "$PINNED_MAILU_VERSION" != "" ] && [ "$BRANCH" == "master" ]
#then
  #images=$(docker-compose -f tests/build.yml config | awk -F ':' '/image:/{ print $2 }')
  #for image in $images
  #do
  #  docker tag "${image}":"${PINNED_MAILU_ARCH_VERSION}" "${image}":${MAILU_VERSION}
  #done
#Push MAILU_VERSION images
  #PINNED_MAILU_ARCH_VERSION=$MAILU_VERSION
  #docker-compose -f tests/build.yml push
#  exit 0
#fi

#Fallback in case $PINNED_MAILU_VERSION is empty. This should never execute.
docker-compose -f tests/build.yml push
