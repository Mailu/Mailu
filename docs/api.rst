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

The swagger.json file can be retrieved via: https://example.com/api/v1/swagger.json
(WEB_API=/api)
The swagger.json file can be consumed in programs such as Postman for generating all API calls.


In-built SwaggerUI
------------------
The Mailu API comes with an in-built SwaggerUI. It is a web client that allows
anyone to visualize and interact with the Mailu API.

Assuming ``/api`` is configured as value for ``WEB_API``, it
is accessible via the URL: https://example.com/api/


SCIM provisioning
-----------------

Mailu exposes a SCIM 2.0 provisioning endpoint at
``<WEB_API>/scim/v2``. With the default ``WEB_API=/api``, the SCIM base URL is::

  https://example.com/api/scim/v2

The SCIM endpoint uses the same bearer token as the REST API::

  Authorization: Bearer <API_TOKEN>

Supported SCIM resources:

* ``/ServiceProviderConfig``
* ``/ResourceTypes``
* ``/Schemas``
* ``/Bulk`` for up to 100 operations in a request of at most 1 MiB
* ``/Users`` for listing, creating, reading, replacing, patching, and deprovisioning users
* ``/Groups`` for listing, creating, reading, replacing, patching, and deleting
  alias-backed groups

Mailu maps SCIM users to mailbox users:

* ``userName`` is the mailbox email address.
* ``displayName`` or ``name.formatted`` maps to the Mailu displayed name.
* ``active`` maps to the Mailu enabled flag.
* ``password`` sets the mailbox password only during creation. If no password
  is supplied, Mailu generates a random mailbox password. SCIM cannot change
  an existing mailbox password (``changePassword.supported`` is false).
* Mailbox email addresses are also used as SCIM ``id`` values. Mailbox rename
  and persistent client ``externalId`` correlation are not supported.

SCIM user creation requires the mailbox domain to already exist in Mailu. Mailu does not create domains from SCIM requests. SCIM ``DELETE`` deprovisions users by disabling the mailbox instead of deleting mailbox data.

Mailu maps SCIM groups to aliases:

* The group ``id`` is the alias email address. On creation, Mailu uses ``id``
  when supplied; otherwise ``displayName`` must contain the alias email
  address. Mailu cannot derive an alias domain from an arbitrary human group
  label. Accepting the client-supplied ``id`` here is a Mailu mapping
  extension; core SCIM normally treats ``id`` as server-assigned.
* ``members[].value`` entries map directly to the alias ``destination`` list.
  Destinations are email addresses and may refer to local Mailu users or
  external forwarding addresses.
* ``PUT`` replaces the alias destination list. ``PATCH`` can add, replace, or
  remove destinations. ``DELETE`` deletes the alias.
* The alias domain must already exist, and normal Mailu alias limits still
  apply.
* ``/Groups`` is a direct view of Mailu aliases, not a separate set of
  SCIM-managed records. Existing aliases are therefore visible and can be
  changed or deleted through the Group endpoints.

SCIM user and group responses include the current entity tag in both
``meta.version`` and the HTTP ``ETag`` header. Clients can send that value in
``If-Match`` on ``PUT``, ``PATCH``, and ``DELETE``. Mailu rejects stale values
with ``412 Precondition Failed`` without applying the requested change.
Conditional reads support ``If-Match`` and ``If-None-Match``; a matching
``If-None-Match`` returns ``304 Not Modified``.

Resource ``POST`` and ``PUT`` bodies must contain exactly the corresponding
User or Group schema URI. ``PATCH`` bodies must contain exactly the PatchOp
schema URI, and a Bulk request must contain exactly the BulkRequest schema URI.
Each Bulk operation's ``data`` object has the same schema requirement as the
equivalent direct operation. Schema URI comparisons are case-insensitive;
duplicates and unsupported extensions are rejected. ``bulkId`` references are
substituted only after the referenced resource is created; circular dependency
graphs are rejected rather than guessed.

User and Group endpoints support the mutually exclusive ``attributes`` and
``excludedAttributes`` projection parameters on every response that returns a
resource. Comma-separated top-level and supported sub-attribute paths are
accepted. ``schemas`` and ``id`` are always returned, while ``password`` is
never returned. Projection does not remove HTTP ``ETag`` or
``Content-Location`` headers. Discovery endpoints ignore these query
parameters as required by RFC 7644.

User ``DELETE`` retains mailbox data by setting ``active`` to false. The
disabled User remains visible to SCIM reads and can be reactivated. This is a
Mailu deprovisioning behavior, not RFC 7644 tombstone semantics.

List filtering is limited to ``userName eq "..."`` for Users and
``displayName eq "..."`` for Groups. Attribute names and ``eq`` are
case-insensitive. Because this compatibility subset is not the RFC 7644 filter
grammar, ``ServiceProviderConfig`` advertises filtering as unsupported; clients
must not infer general filter support from these two accepted forms.

For authentik, create a SCIM provider for the Mailu application and configure:

* SCIM base URL: ``https://example.com/api/scim/v2``
* Authentication mode: static token
* Token: the Mailu ``API_TOKEN`` value
