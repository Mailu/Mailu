# try create, find, lookup, delete

echo "Start 05_test_alias_interfaces.sh"

# Try creating a new alias /alias
curl --silent --insecure -X 'POST' \
  'https://localhost/api/v1/alias' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "comment": "test alias for user@mailu.io and admin@mailu.io",
  "destination": [
    "user@mailu.io",
    "admin@mailu.io"
  ],
  "wildcard": false,
  "email": "test@mailu.io"
}' | grep 200
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Created alias test@mailu.io succcessfully for user@mailu.io and admin@mailu.io"

curl --silent --insecure -X 'POST' \
  'https://localhost/api/v1/alias' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "comment": "test2 alias for user@mailu.io",
  "destination": [
    "user@mailu.io"
  ],
  "wildcard": false,
  "email": "test2@mailu.io"
}' | grep 200
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Created alias test2@mailu.io succcessfully for user@mailu.io "

# Try retrieving all aliases /alias. We expect to retrieve 2
curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/alias' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep -o '"destination":' | grep -c '"destination":' | grep 2
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Successfully retrieved 2 aliases"

# Try looking up the aliases for a specific domain /alias/destination/{domain}. We expect to retrieve 2
curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/alias/destination/mailu.io' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep -o '"destination":' | grep -c '"destination":' | grep 2
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Successfully retrieved 2 aliases"

# Try deleting a specific alias /alias/{alias}
curl --silent --insecure -X 'DELETE' \
  'https://localhost/api/v1/alias/test2%40mailu.io' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep 200
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Deleted alias test2@mailu.io succcessfully"

# Try updating a specific alias /alias/{alias}
curl --silent --insecure -X 'PATCH' \
  'https://localhost/api/v1/alias/test%40mailu.io' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "comment": "updated_comment",
  "destination": [
    "user@mailu.io"
  ],
  "wildcard": true
}' | grep 200
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Updated alias test2@mailu.io succcessfully"

# Try looking up a specific alias /alias/{alias}.
#Check if values were updated correctyly in previous step.
response=$(curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/alias/test%40mailu.io' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest')
echo $response | grep 'admin@mailu.io'
if [ $? -ne 1 ]; then
  exit 1
fi
echo "Confirmed that destination admin@mailu.io is removed from alias test@mailu.io"
echo $response | grep 'updated_comment'
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Confirmed that comment attribute is updated successfully"

echo "Finished 05_test_alias_interfaces.sh"