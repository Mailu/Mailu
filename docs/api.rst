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


In-built SwaggerUI
------------------
The Mailu API comes with an in-built SwaggerUI. It is a web client that allows
anyone to visualize and interact with the Mailu API.

Assuming ``/api`` is configured as value for ``WEB_API``, it
is accessible via the URL: https://myserver/api/


SCIM provisioning
-----------------

Mailu exposes a SCIM 2.0 user provisioning endpoint at
``<WEB_API>/scim/v2``. With the default ``WEB_API=/api``, the SCIM base URL is::

  https://myserver/api/scim/v2

The SCIM endpoint uses the same bearer token as the REST API::

  Authorization: Bearer <API_TOKEN>

Supported SCIM resources:

* ``/ServiceProviderConfig``
* ``/ResourceTypes``
* ``/Schemas``
* ``/Users`` for listing, creating, reading, replacing, patching, and deprovisioning users
* ``/Groups`` returns an empty list; group provisioning is not supported

Mailu maps SCIM users to mailbox users:

* ``userName`` is the mailbox email address.
* ``displayName`` or ``name.formatted`` maps to the Mailu displayed name.
* ``active`` maps to the Mailu enabled flag.
* ``password`` sets the mailbox password when supplied. If no password is supplied during creation, Mailu generates a random mailbox password.

SCIM user creation requires the mailbox domain to already exist in Mailu. Mailu does not create domains from SCIM requests. SCIM ``DELETE`` deprovisions users by disabling the mailbox instead of deleting mailbox data.

For authentik, create a SCIM provider for the Mailu application and configure:

* SCIM base URL: ``https://myserver/api/scim/v2``
* Authentication mode: static token
* Token: the Mailu ``API_TOKEN`` value
