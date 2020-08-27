cat << EOF | docker-compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu config-update --verbose
users:
  - localpart: replyuser
    password_hash: "\$1\$F2OStvi1\$Q8hBIHkdJpJkJn/TrMIZ9/"
    hash_scheme: MD5-CRYPT
    domain: mailu.io
    reply_enabled: true
    reply_subject: This will not reach me
    reply_body: Cause this is just a test
EOF

python3 tests/reply_test.py

cat << EOF | docker-compose -f tests/compose/core/docker-compose.yml exec -T admin flask mailu config-update --verbose
users:
  - localpart: replyuser
    password_hash: "\$1\$F2OStvi1\$Q8hBIHkdJpJkJn/TrMIZ9/"
    hash_scheme: MD5-CRYPT
    domain: mailu.io
    reply_enabled: false
EOF
