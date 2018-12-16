#!/bin/bash

docker login -u $DOCKER_UN -p $DOCKER_PW
docker-compose -f tests/build.yml push
