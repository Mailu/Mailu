#!/bin/bash -x
# Small script to deploy locally built images to a remote docker
compose_options=$1
images=$(docker-compose $1 images  | awk 'NR > 2 { printf $2":"$3" " }')
docker save $images | pigz  - > mail.local.tgz
echo "now run 'docker -H \"ssh://user@host\" load -i mail.local.tgz"
