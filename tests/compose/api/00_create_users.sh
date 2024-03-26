# create user admin@maiu.io
echo "Create users"

curl --silent --insecure -X 'POST' \
  'https://localhost/api/v1/domain' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "mailu.io",
  "comment": "internal domain for testing",
  "max_users": -1,
  "max_aliases": -1,
  "max_quota_bytes": 0,
  "signup_enabled": false
}' | grep 200

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Domain mail.io has been created successfully"

curl --silent --insecure -X 'POST' \
  'https://localhost/api/v1/user' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "admin@mailu.io",
  "raw_password": "password",
  "comment": "created for testing RESTful API",
  "global_admin": true,
  "enabled": true,
  "change_pw_next_login": false,
  "enable_imap": true,
  "enable_pop": true,
  "allow_spoofing": false,
  "forward_enabled": false,
  "reply_enabled": false,
  "displayed_name": "admin",
  "spam_enabled": true,
  "spam_mark_as_read": true
}' | grep 200

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Created admin user (admin@mailu.io) successfully"

# Test if creating duplicate returns 409 HTTP response.
curl --silent --insecure -X 'POST' \
  'https://localhost/api/v1/user' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "admin@mailu.io",
  "raw_password": "password",
  "comment": "created for testing RESTful API",
  "global_admin": true,
  "enabled": true,
  "change_pw_next_login": false,
  "enable_imap": true,
  "enable_pop": true,
  "allow_spoofing": false,
  "forward_enabled": false,
  "reply_enabled": false,
  "displayed_name": "admin",
  "spam_enabled": true,
  "spam_mark_as_read": true
}' | grep 409

if [ $? -ne 0 ]; then
  exit 1
fi
echo "OK. Failed creating duplicate user."

# create user user@mailu.io
curl --silent --insecure -X 'POST' \
  'https://localhost/api/v1/user' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "user@mailu.io",
  "raw_password": "password",
  "comment": "created for testing RESTful API",
  "global_admin": false,
  "enabled": true,
  "change_pw_next_login": false,
  "enable_imap": true,
  "enable_pop": true,
  "allow_spoofing": false,
  "forward_enabled": false,
  "reply_enabled": false,
  "displayed_name": "admin",
  "spam_enabled": true,
  "spam_mark_as_read": true
}' | grep 200

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Created user (user@mailu.io) successfully"

echo "Finished 00_create_users.sh"