set -e
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu user add admin@mailu.io 'password'
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu user add user@mailu.io 'password'
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu user add 'user/with/slash'@mailu.io 'password'
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu user add user_UTF8@mailu.io 'pa…ss%e9word€'
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu user add forwardinguser@mailu.io 'password'
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu user add replyuser@mailu.io 'password'
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu user add '测试2@mailu.io' 'password'
