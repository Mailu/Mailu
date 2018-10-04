#!/bin/bash
for file in tests/compose/*.env ; do
	cp $file .env
	docker-compose -f tests/compose/run.yml up -d
done
sleep 2m
