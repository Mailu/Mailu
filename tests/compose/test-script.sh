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
	fetchmail
	front
)

#Colors (bold)
YEL='\e[1;33m'
RED='\e[1;31m'
RES='\e[0m'

# Compose file to use
DC_FILE="tests/compose/run.yml"

# Time to sleep in minutes after starting the containers
WAIT=5

containers_check() {
	status=0
	for container in "${containers[@]}"; do
		name="${DOCKER_ORG}_${container}_1"
		echo -e "\n${YEL}Checking ${name}${RES}"
		if ! docker inspect "$name" | grep '"Status": "running"'; then
			echo -e "${RED}Fail!${RES}"
			status=1
		fi
	done
	docker ps -a
	return $status
}

container_logs() {
	for container in "${containers[@]}"; do
                echo -e "\n${YEL}Showing logs for ${container}${RES}"
                docker-compose -f $DC_FILE -p $DOCKER_ORG logs -t $container
        done
}

clean() {
	docker-compose -f $DC_FILE -p $DOCKER_ORG down || exit 1
	rm -fv .env
}

# Cleanup before callig exit
die() {
	clean
	exit $1
}

for file in tests/compose/*.env ; do
	echo -e "\n${YEL}Starting test for ${file}${RES}"
	cp -v $file .env
	docker-compose -f $DC_FILE -p $DOCKER_ORG up -d || die 1

	# Clean terminal distortion from docker-compose in travis
	echo -e "\n${YEL}Sleeping for ${WAIT} minutes${RES}\n"

	travis_wait sleep ${WAIT}m || sleep ${WAIT}s # Fallback sleep for local run

	container_logs
	containers_check || die 1
	clean
done

