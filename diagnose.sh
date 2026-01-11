#!/bin/bash
# Mailu Deployment Diagnostics

echo "=========================================="
echo "Mailu Deployment Diagnostics"
echo "=========================================="
echo ""

echo "1. Checking Docker containers..."
docker ps | grep mail-server-app-cpkd3a || echo "No containers found!"
echo ""

echo "2. Checking port bindings..."
docker ps --format "table {{.Names}}\t{{.Ports}}" | grep mail-server-app-cpkd3a
echo ""

echo "3. Testing local access to admin (inside server)..."
curl -I http://localhost:8080/admin 2>&1 | head -n 5
echo ""

echo "4. Testing local access to webmail (inside server)..."
curl -I http://localhost:8080/webmail 2>&1 | head -n 5
echo ""

echo "5. Checking firewall status..."
if command -v ufw &> /dev/null; then
    echo "UFW Status:"
    ufw status | grep -E "8080|8443|80|443"
elif command -v firewall-cmd &> /dev/null; then
    echo "Firewalld Status:"
    firewall-cmd --list-ports
else
    echo "No firewall tool detected (ufw/firewall-cmd)"
fi
echo ""

echo "6. Checking listening ports..."
netstat -tuln | grep -E ":8080|:8443|:25|:587|:993" || ss -tuln | grep -E ":8080|:8443|:25|:587|:993"
echo ""

echo "7. Checking front container logs (last 20 lines)..."
docker logs --tail 20 mail-server-app-cpkd3a-front-1 2>&1
echo ""

echo "8. Checking admin container logs (last 20 lines)..."
docker logs --tail 20 mail-server-app-cpkd3a-admin-1 2>&1
echo ""

echo "=========================================="
echo "Diagnostic complete!"
echo "=========================================="
