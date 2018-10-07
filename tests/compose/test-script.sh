#!/bin/bash
containers=(
	webmail
	imap
	smtp
	antispam
	admin
	redis
	antivirus
	webdav
#	fetchmail
	front
)

# Time to sleep in minutes after starting the containers
WAIT=1

containers_check() {
	status=0
	for container in "${containers[@]}"; do
		name="${DOCKER_ORG}_${container}_1"
		echo "Checking $name"
		docker inspect "$name" | grep '"Status": "running"' || status=1
	done
	docker ps -a
	return $status
}

container_logs() {
	for container in "${containers[@]}"; do
		name="${DOCKER_ORG}_${container}_1"
                echo "Showing logs for $name"
                docker container logs "$name"
        done
}

clean() {
	docker-compose -f tests/compose/run.yml -p $DOCKER_ORG down || exit 1
	rm -fv .env
}

# Cleanup before callig exit
die() {
	clean
	exit $1
}

for file in tests/compose/*.env ; do
	cp $file .env
	docker-compose -f tests/compose/run.yml -p $DOCKER_ORG up -d
	echo -e "\nSleeping for ${WAIT} minutes" # Clean terminal distortion from docker-compose in travis
	travis_wait sleep ${WAIT}m || sleep ${WAIT}m #Fallback sleep for local run
	container_logs
	containers_check || die 1
	clean
done

