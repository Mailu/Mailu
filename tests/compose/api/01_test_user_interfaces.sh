echo "Test user interfaces"
# create user user@mailu.io for testing deletion
curl --silent --insecure -X 'POST' \
  'https://localhost/api/v1/user' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "user2@mailu.io",
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
echo "created user (user2@mailu.io) successfully"

#delete user2@mailu.io
curl --silent --insecure -X 'DELETE' \
  'https://localhost/api/v1/user/user2%40mailu.io' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  | grep 200

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Deleted user2 (user2@mailu.io) successfully"

#Check if updating user works
curl --silent --insecure -X 'PATCH' \
  'https://localhost/api/v1/user/user%40mailu.io' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "comment": "updated_comment"
}' | grep 200

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Updated user(user@mailu.io) successfully"

curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/user/user%40mailu.io' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  | grep updated_comment

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Confirmed that comment attribute of user was correctly updated"

# try get all users. At this moment we should have 2 users total
curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/user' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  | grep -o "email" | grep -c "email" | grep 2

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Retrieved all users successfully"

echo "Finished 01_test_user_interfaces.sh"