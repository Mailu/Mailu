Mailu RESTful API
=================

Mailu offers a RESTful API for changing the Mailu configuration.
Anything that can be configured via the Mailu web administration interface,
can also be configured via the API.

The Mailu API is disabled by default. It can be enabled and configured via
the settings:

* ``API``
* ``WEB_API``
* ``API_TOKEN``

For more information see the section :ref:`Advanced configuration <advanced_settings>`
in the configuration reference.


Swagger.json
------------

The swagger.json file can be retrieved via: https://myserver/api/v1/swagger.json.
The swagger.json file can be consumed in programs such as Postman for generating all API calls.


In-built SwaggerUI
------------------
The Mailu API comes with an in-built SwaggerUI. It is a web client that allows
anyone to visualize and interact with the Mailu API.

It is accessible via the URL: https://myserver/api/v1/swaggerui
