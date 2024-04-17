echo "Start 04_test_relay_interfaces.sh"

# Try creating a new relay /relay
curl --silent --insecure -X 'POST' \
  'https://localhost/api/v1/relay' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "relay1.mailu.io",
  "smtp": "relay1.mailu.io:8755",
  "comment": "backup relay1"
}' | grep 200
if [ $? -ne 0 ]; then
  exit 1
fi
echo "created a relay for domain relay1.mailu.io successfully"

curl --silent --insecure -X 'POST' \
  'https://localhost/api/v1/relay' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "relay2.mailu.io",
  "comment": "backup relay2"
}' | grep 200
if [ $? -ne 0 ]; then
  exit 1
fi
echo "created a relay for domain relay2.mailu.io successfully"

# Try retrieving all relays /relay. We expect to retrieve 2 in total
curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/relay' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep -o '"name":' | grep -c '"name":' | grep 2
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Retrieved all relays (2 in total) successfully"

# Try looking up a specific relay /relay/{name}
curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/relay/relay1.mailu.io' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep '"name": "relay1.mailu.io"'
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Retrieved the specified relay (relay1.mailu.io) successfully"

# Try deleting a specific relay /relay/{name}
curl -silent --insecure -X 'DELETE' \
  'https://localhost/api/v1/relay/relay2.mailu.io' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep 200
if [ $? -ne 0 ]; then
  exit 1
fi
echo "Deleted relay2.mailu.io successfully"

curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/relay' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep -o '"name":' | grep -c '"name":' | grep 1
if [ $? -ne 0 ]; then
  exit 1
fi
echo "confirmed we only have 1 relay now"

# Try updating a specific relay /relay/{name}
curl --silent --insecure -X 'PATCH' \
  'https://localhost/api/v1/relay/relay1.mailu.io' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "smtp": "anotherName",
  "comment": "updated_comment"
}' | grep 200
if [ $? -ne 0 ]; then
  exit 1
fi
echo "update of relay was succcessful"

curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/relay/relay1.mailu.io' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep anotherName | grep updated_comment
echo "confirmed that smtp attribute and comment attribute were correctly updated"

echo "Finished 04_test_relay_interfaces.sh"