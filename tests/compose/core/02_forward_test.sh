cat << EOF | docker-compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu config-update --verbose
users:
  - localpart: forwardinguser
    password_hash: "\$1\$F2OStvi1\$Q8hBIHkdJpJkJn/TrMIZ9/"
    hash_scheme: MD5-CRYPT
    domain: mailu.io
    forward_enabled: true
    forward_destination: ["user@mailu.io"]
EOF

python3 tests/forward_test.py

cat << EOF | docker-compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu config-update --verbose
users:
  - localpart: forwardinguser
    password_hash: "\$1\$F2OStvi1\$Q8hBIHkdJpJkJn/TrMIZ9/"
    hash_scheme: MD5-CRYPT
    domain: mailu.io
    forward_enabled: false
    forward_destination: []
EOF
