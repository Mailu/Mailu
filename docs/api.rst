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
* ``API_TOKEN`` - API token for authentication (with minimum length of 3 characters)

For more information refer to the detailed descriptions in the
:ref:`configuration reference <advanced_settings>`.


Swagger.json
------------

The swagger.json file can be retrieved via: https://myserver/api/v1/swagger.json
(WEB_API=/api)
The swagger.json file can be consumed in programs such as Postman for generating all API calls.

Passkey policy and account setup
--------------------------------

The versioned API exposes ``passkey_require_enrollment`` on domain create,
read, and update operations. User create, read, and update operations expose
``passkey_enroll_next_login``. These fields use the same policy as the
corresponding domain and user administration forms. ``raw_password`` is
optional when creating a user, so an account can be created for setup through
a one-time link without first assigning a password.

To generate or replace a one-time account setup or recovery link, send an
authenticated ``POST`` request to ``/api/v1/user/{email}/setup-link``. The
response contains the URL and its UTC expiration time. Generating a replacement
invalidates any previous link for that user. The link can set a password or add
a passkey according to the account's policy and the configured
``ACCOUNT_SETUP_TOKEN_TTL``.


In-built SwaggerUI
------------------
The Mailu API comes with an in-built SwaggerUI. It is a web client that allows
anyone to visualize and interact with the Mailu API.

Assuming ``/api`` is configured as value for ``WEB_API``, it
is accessible via the URL: https://myserver/api/
