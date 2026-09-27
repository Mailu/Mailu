#!/bin/sh
set -eu

docker compose -f tests/compose/core/docker-compose.yml exec -T front python3 - TestEnvironment TestConf < core/base/libs/socrate/test.py
docker compose -f tests/compose/core/docker-compose.yml exec -T front python3 < tests/front_pid_reload.py
