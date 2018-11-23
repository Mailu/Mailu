echo "Creating users ..."
docker-compose -f tests/compose/core/docker-compose.yml exec admin flask mailu admin admin mailu.io password || exit 1
docker-compose -f tests/compose/core/docker-compose.yml exec admin flask mailu user --hash_scheme='SHA512-CRYPT' user mailu.io 'password' || exit 1
echo "Admin and user successfully created!"