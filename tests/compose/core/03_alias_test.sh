cat << EOF | docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu config-update -v 1
aliases:
  - localpart: alltheusers
    domain: mailu.io
    destination: "admin@mailu.io,user@mailu.io,user/with/slash@mailu.io"
EOF

python3 tests/alias_test.py

cat << EOF | docker compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu config-update -v 1
aliases: []
EOF
