echo "Creating users ..."
docker-compose -f tests/compose/core/docker-compose.yml exec admin flask mailu admin admin mailu.io password || exit 1
docker-compose -f tests/compose/core/docker-compose.yml exec admin flask mailu user user mailu.io 'password' 'SHA512-CRYPT' || exit 1
echo "Admin and user successfully created!"
