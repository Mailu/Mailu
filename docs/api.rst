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
* ``id`` is an immutable provider identifier. Users that existed before the
  persistent-identity migration retain their already-published email ID; newly
  created resources receive a UUID. Client-supplied ``id`` values are ignored.
* ``externalId`` is preserved as a case-exact client correlation value and can
  be created, replaced, patched, and used by the supported equality filter.

SCIM user creation requires the mailbox domain to already exist in Mailu.
Mailu does not create domains from SCIM requests. User ``DELETE`` tombstones
the SCIM resource: every later operation on the old ID returns ``404`` and
list results omit it. Mailbox data may remain in a disabled Mailu User below
the SCIM boundary, but browser sessions, application tokens, and Mailu
administrator grants are revoked. Re-provisioning the same ``userName``
is rejected: the retained mailbox and tombstone permanently reserve that
routing address, so old principal authority cannot transfer to a new SCIM
identity.

Mailu maps explicitly SCIM-managed Groups to aliases. Ordinary Mailu aliases
are not Groups and are neither listed nor mutable through SCIM. A retained
legacy alias can be transferred into exclusive SCIM ownership during the
maintenance window with::

  flask mailu scim-group-adopt alias@example.com

Adoption accepts only an enabled, unowned, non-wildcard alias and blocks later
ordinary alias edits. It is deliberately explicit: the old implementation
recorded no ownership and exposing every alias to destructive SCIM operations
was unsafe.

Group requests and representations use the core Group schema plus the required
Mailu extension ``https://mailu.io/schemas/scim/2.0/Group``:

* ``displayName`` is the human Group label. It is not an email address.
* The extension's immutable ``aliasAddress`` is the Mailu routing address.
* Core ``members[].value`` entries are active SCIM User or Group IDs.
  Responses include a dereferenceable ``$ref`` and resource ``type``.
* The extension's ``externalDestinations`` contains external forwarding
  addresses. A local Mailu User or Alias must not be placed there; local
  resources use normalized member IDs so cycle and deletion checks remain
  effective.
* ``PUT`` atomically replaces normalized members and external destinations.
  ``PATCH`` supports core member operations and the fully-qualified extension
  path. ``aliasAddress`` cannot be changed. ``DELETE`` tombstones the Group
  ID and deletes its managed Alias.
* The alias domain must already exist, and normal Mailu alias limits still
  apply.
* The materialized Alias destination list is limited to 1023 characters.
  Oversized Group mutations fail before changing the database.

SCIM user and group responses include the current entity tag in both
``meta.version`` and the HTTP ``ETag`` header. Clients can send that value in
``If-Match`` on ``PUT``, ``PATCH``, and ``DELETE``. Mailu rejects stale values
with ``412 Precondition Failed`` without applying the requested change.
Conditional reads support ``If-Match`` and ``If-None-Match``; a matching
``If-None-Match`` returns ``304 Not Modified``.

User ``POST`` and ``PUT`` bodies must contain exactly the User schema URI.
Group ``POST`` and ``PUT`` bodies must contain exactly the core Group and
required Mailu extension URIs. ``PATCH`` bodies contain exactly the PatchOp
schema URI, and a Bulk request contains exactly the BulkRequest schema URI.
Each Bulk operation's ``data`` object has the same schema requirement as the
equivalent direct operation. Schema URI comparisons are case-insensitive;
duplicates and unsupported extensions are rejected. ``bulkId`` references are
substituted only in reference-valued fields such as ``members[].value`` and
resource paths; raw extension destinations beginning with ``bulkId:`` remain
literal. Circular dependency graphs are rejected rather than guessed.

User and Group endpoints support the mutually exclusive ``attributes`` and
``excludedAttributes`` projection parameters on every response that returns a
resource. Comma-separated top-level and supported sub-attribute paths are
accepted, including fully qualified Mailu Group extension paths. ``schemas``
and ``id`` are always returned; Group ``displayName`` is also always returned,
while ``password`` is never returned. Projection does not remove HTTP ``ETag``
or ``Content-Location`` headers. Discovery endpoints ignore these query
parameters as required by RFC 7644.

List filtering is limited to ``userName eq "..."`` or
``externalId eq "..."`` for Users and ``displayName eq "..."`` or
``externalId eq "..."`` for Groups. Attribute names and ``eq`` are
case-insensitive; ``externalId`` values are case-exact. Because this
compatibility subset is not the RFC 7644 filter grammar,
``ServiceProviderConfig`` advertises filtering as unsupported; clients must
not infer general filter support from these accepted forms.

For authentik, create a SCIM provider for the Mailu application and configure:

* SCIM base URL: ``https://example.com/api/scim/v2``
* Authentication mode: static token
* Token: the Mailu ``API_TOKEN`` value
