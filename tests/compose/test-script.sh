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

# Default to mailu for DOCKER_ORG
if [ -z "$DOCKER_ORG" ]; then
	export DOCKER_ORG="mailu"
fi

# Verbose sleep, to prevent Travis to cancel the build
# First argument is desired sleep time in minutes
v_sleep() {
	COUNT=$1
	until [ $COUNT -eq 0 ]; do
		echo "Sleep for $COUNT more minutes"
		sleep 1m
		((COUNT--))
	done;
}

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
	v_sleep 1
	container_logs
	containers_check || die 1
	clean
done

