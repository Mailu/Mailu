from mailu import app

import sys
import tabulate


# Known endpoints without permissions
known_missing_permissions = [
    "index",
    "static", "bootstrap.static",
    "admin.static", "admin.login"
]


# Compute the permission table
missing_permissions = []
permissions = {}
for endpoint, function in app.view_functions.items():
    audit = function.__dict__.get("_audit_permissions")
    if audit:
        handler, args = audit
        if args:
            model = args[0].__name__
            key = args[1]
        else:
            model = key = None
        permissions[endpoint] = [endpoint, handler.__name__, model, key]
    elif endpoint not in known_missing_permissions:
        missing_permissions.append(endpoint)


# Fail if any endpoint is missing a permission check
if missing_permissions:
    print("The following endpoints are missing permission checks:")
    print(missing_permissions.join(","))
    sys.exit(1)


# Display the permissions table
print(tabulate.tabulate([
    [route, *permissions[route.endpoint]]
    for route in app.url_map.iter_rules() if route.endpoint in permissions
]))
