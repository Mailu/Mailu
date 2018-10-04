#!/bin/bash
for file in ../*.env ; do
	cp $file .env
	docker-compose -f ../run.yml up -d
done
