#!/bin/bash
containers_check() {
	for container in mailu_webmail_1 mailu_imap_1 mailu_smtp_1 mailu_antispam_1 mailu_admin_1 mailu_redis_1 mailu_antivirus_1 mailu_webdav_1 mailu_fetchmail_1 mailu_front_1; do
	        docker inspect $container | grep '"Status": "running"' || exit 1
	done
}

for file in tests/compose/*.env ; do
	cp $file .env
	docker-compose -f tests/compose/run.yml up -d
	sleep 1m
	containers_check
done

