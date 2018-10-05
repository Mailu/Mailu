#!/bin/bash
containers=(
	mailu_webmail_1
	mailu_imap_1
	mailu_smtp_1
	mailu_antispam_1
	mailu_admin_1
	mailu_redis_1
	mailu_antivirus_1
	mailu_webdav_1
#	mailu_fetchmail_1
	mailu_front_1
)

containers_check() {
	STATUS=0
	for container in "${containers[@]}"; do
		echo "Checking $container"
		docker inspect $container | grep '"Status": "running"' || STATUS=1
	done
	return $STATUS
}

container_logs() {
	for container in "${containers[@]}"; do
                echo "Showing logs for $container"
                docker container logs $container
        done
}

for file in tests/compose/*.env ; do
	cp $file .env
	docker-compose -f tests/compose/run.yml up -d
	sleep 1m
	docker ps
	container_logs
	containers_check || exit 1
done

