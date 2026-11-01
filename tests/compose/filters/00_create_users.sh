echo "Creating user required for next test ..."
# Should not fail and update the password; update mode
docker compose -f tests/compose/filters/docker-compose.yml exec -T admin flask mailu user add admin@mailu.io 'password' || exit 1
docker compose -f tests/compose/filters/docker-compose.yml exec -T admin flask mailu admin add admin@mailu.io || exit 1
docker compose -f tests/compose/filters/docker-compose.yml exec -T admin flask mailu user add user@mailu.io 'password' || exit 1
echo "User created successfully"
