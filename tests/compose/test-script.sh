#!/bin/bash
containers=(
	webmail_1
	imap_1
	smtp_1
	antispam_1
	admin_1
	redis_1
	antivirus_1
	webdav_1
	fetchmail_1
	front_1
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
	v_sleep 1
	STATUS=0
	for container in "${containers[@]}"; do
		echo "Checking ${DOCKER_ORG}_${container}"
		docker inspect "${DOCKER_ORG}_${container}" | grep '"Status": "running"' || STATUS=1
	done
	docker ps -a
	return $STATUS
}

container_logs() {
	for container in "${containers[@]}"; do
                echo "Showing logs for ${DOCKER_ORG}_${container}"
                docker container logs "${DOCKER_ORG}_${container}"
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
	container_logs
	containers_check || die 1
	clean
done

