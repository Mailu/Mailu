set -e
echo "Users tests ..."
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu user add admin@mailu.io 'password'
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu admin add admin@mailu.io
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu admin remove admin@mailu.io
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu admin add admin@mailu.io
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu user add user@mailu.io 'password'
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu user add 'user/with/slash'@mailu.io 'password'
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu user add user_UTF8@mailu.io 'pa…ss%e9word€'
echo "User testing successful!"
