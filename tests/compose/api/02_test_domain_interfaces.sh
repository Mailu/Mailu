echo "Test Domain interfaces"

curl --silent --insecure -X 'POST' \
  'https://localhost/api/v1/domain' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "mailu2.io",
  "comment": "internal domain for testing",
  "max_users": -1,
  "max_aliases": -1,
  "max_quota_bytes": 0,
  "signup_enabled": false
}' | grep 200

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Domain mail2.io has been created successfully"

curl --silent --insecure -X 'PATCH' \
  'https://localhost/api/v1/domain/mailu2.io' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "comment": "updated_domain"
}' | grep 200

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Domain mail2.io has been updated"

curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/domain/mailu2.io' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep updated_domain

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Confirmed that comment attribute of domain mailu2.io was correctly updated"

# try get all domains. At this moment we should have 2 domains total
curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/domain' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  | grep -o "name" | grep -c "name" | grep 2

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Retrieved all domains successfully"

# try create dkim keys
curl --silent --insecure -X 'POST' \
  'https://mailutest/api/v1/domain/mailu2.io/dkim' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  -d '' \
  | grep 200

if [ $? -ne 0 ]; then
  exit 1
fi
echo "dkim keys were created successfully for domain mailu2.io"

# try deleting a domain
curl --silent --insecure -X 'DELETE' \
  'https://localhost/api/v1/domain/mailu2.io' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  | grep 200

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Domain mailu2.io was deleted successfully"

# try looking up all users of a domain. There should be 2 users.
curl --silent --insecure -X 'GET' \
  'https://mailutest/api/v1/domain/mailu.io/users' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep -o "email" | grep -c "email" | grep 2

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Retrieved all users of domain mailu.io successfully"


#### Alternatives

#try to create an alternative
curl --silent --insecure -X 'POST' \
  'https://mailutest/api/v1/alternative' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "mailu2.io",
  "domain": "mailu.io"
}' | grep 200

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Alternative mailu2.io for domain mailu.io was created successfully"

# try get all alternatives. At this moment we should have 1 alternative total
curl --silent --insecure -X 'GET' \
  'https://localhost/api/v1/alternative' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer apitest' \
  | grep -o "name" | grep -c "name" | grep 1

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Retrieved all alternatives successfully"

# try to check if an alternative exists
curl --silent --insecure -X 'GET' \
  'https://mailutest/api/v1/alternative/mailu2.io' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest' \
  | grep '{"name": "mailu2.io", "domain": "mailu.io"}'

if [ $? -ne 0 ]; then
  exit 1
fi
echo "Lookup for alternative mailu2.io was successful"

# try to delete an alternative
curl --silent --insecure -X 'DELETE' \
  'https://mailutest/api/v1/alternative/mailu2.io' \
  -H 'accept: application/json' \
  -H 'Authorization: apitest'

echo "Finshed 02_test_domain_interfaces.sh"