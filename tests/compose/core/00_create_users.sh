echo "Users tests ..."
# Should fail, admin is already auto-created
docker-compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu admin admin mailu.io 'FooBar' && exit 1
echo "The above error was intended!"
# Should not fail, but does nothing; ifmissing mode
docker-compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu admin admin mailu.io 'FooBar' --mode=ifmissing || exit 1
# Should not fail and update the password; update mode
docker-compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu admin admin mailu.io 'password' --mode=update || exit 1
docker-compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu user user mailu.io 'password' || exit 1
docker-compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu user 'user/with/slash' mailu.io 'password' || exit 1
echo "User testing successful!"
