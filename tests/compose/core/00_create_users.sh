set -e
echo "Users tests ..."
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu admin add admin@mailu.io
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu admin remove admin@mailu.io
docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu admin add admin@mailu.io
echo "User testing successful!"
