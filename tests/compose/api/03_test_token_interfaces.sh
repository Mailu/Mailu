echo "start token tests"

# Try creating a token /token
curl --silent --insecure -X 'POST' \
  'https://localhost/api/v1/token' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "user@mailu.io",
  "comment": "my token related comment",
  "AuthorizedIP": [
    "203.0.113.0/24",
    "203.2.114.2/32"
  ]
}' | grep '"token": "'
if [ $? -ne 0 ]; then
  exit 1
fi
echo "created a token for user@mailu.io successfully"

# Try create a token for a specific user /tokenuser/{email}
curl --silent --insecure -X 'POST' \
  'https://localhost/api/v1/tokenuser/user%40mailu.io' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "comment": "token test"
}' | grep '"token": "'
if [ $? -ne 0 ]; then
  exit 1
fi
echo "created a second token for user@mailu.io successfully"

# Try retrieving all tokens /token. We expect to retrieve 2 in total.
curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/token' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep -o "id" | grep -c "id" | grep 2
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Retrieved all tokens (2 in total) successfully"

# Try finding a specific token /token/{token_id}
curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/token/2' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
   | grep '"id": 2'
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Retrieved token with id 2 successfully"

# Try deleting a token /token/{token_id}
curl --silent --insecure -X 'DELETE' \
  'https://localhost/api/v1/token/1' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep 200
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Deleted token with id 1 successfully"

# Try updating a token /token/{token_id}
curl --silent --insecure -X 'PATCH' \
  'https://localhost/api/v1/token/2' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "comment": "updated_comment",
  "AuthorizedIP": [
    "203.0.112.0/24"
  ]
}' | grep 200
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Updated token with id 2 successfully"

curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/token/2' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
   | grep 'comment": "updated_comment"'
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Confirmed that comment field of token with id 2 was correctly updated"

# Try looking up all tokens of a specific user /tokenuser/{email}
curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/tokenuser/user%40mailu.io' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep -o "id" | grep -c "id" | grep 1
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Retrieved all tokens (1 in total) for user@mailu.io successfully"

echo "Finished 03_test_token_interfaces.sh"