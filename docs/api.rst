.. _mailu_restful_api:

Mailu RESTful API
=================

Mailu offers a RESTful API for changing the Mailu configuration.
Anything that can be configured via the Mailu web administration interface,
can also be configured via the API.

The Mailu API can be configured via the setup utility (setup.mailu.io).
It can also be manually configured via mailu.env:

* ``API`` - Expose the API interface (value: true, false)
* ``WEB_API`` - Path to the API interface
* ``API_TOKEN`` - API token for authentication

For more information refer to the detailed descriptions in the
:ref:`configuration reference <advanced_settings>`.


Swagger.json
------------

The swagger.json file can be retrieved via: https://myserver/api/v1/swagger.json
(WEB_API=/api)
The swagger.json file can be consumed in programs such as Postman for generating all API calls.


In-built SwaggerUI
------------------
The Mailu API comes with an in-built SwaggerUI. It is a web client that allows
anyone to visualize and interact with the Mailu API.

Assuming ``/api`` is configured as value for ``WEB_API``, it
is accessible via the URL: https://myserver/api/
