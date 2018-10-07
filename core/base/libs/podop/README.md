Podop is a piece of middleware designed to run between Postfix or Dovecot
on one side, any Python implementation of a table lookup protocol on the
other side.

It is thus able to forward Postfix maps and Dovecot dicts to the same
(or multiple) backends in order to write a single, more flexible backend
for a mail distribution.

Examples
========

- Connect Postfix to a DNS lookup so that every domain that has a proper MX
  record to your Postfix is actually accepted as a local domain
- Connect both Postfix and Dovecot to an HTTP microservice to run a high
  availability microservice-based mail service
- Use a single database server running any Python-compatible API for both
  your Postfix and Dovecot servers

Configure Podop tables
======================

Podop tables are configured through CLI arguments when running the server.
You must provide a ``--name`` for the table, a ``--type`` for the table and
a ``--param`` that parametrizes the map.

URL table
---------

The URL table will initiate an HTTP GET request for read access and an HTTP
POST request for write access to a table. The table is parametrized with
a template URL containing ``§`` (or ``{}``) for inserting the table key.

```
--name test --type url --param http://microservice/api/v1/map/tests/§
```

GET requests should return ``200`` and a JSON-encoded object
that will be passed either to Postfix or Dovecot. They should return ``4XX``
for access issues that will result in lookup miss, and ``5XX`` for backend
issues that will result in a temporary failure.

POST requests will contain a JSON-encoded object in the request body, that
will be saved in the table.

Postfix usage
=============

In order to access Podop tables from Postfix, you should setup ``socketmap``
Postfix maps. For instance, in order to access the ``test`` table on a Podop
socket at ``/tmp/podop.socket``, use the following setup:

```
virtual_alias_maps = socketmap:unix:/tmp/podop.socket:test
```

Multiple maps or identical maps can be configured for various usages.

```
virtual_alias_maps = socketmap:unix:/tmp/podop.socket:alias
virtual_mailbox_domains = socketmap:unix:/tmp/podop.socket:domain
virtual_mailbox_maps = socketmap:unix:/tmp/podop.socket:alias
```

In order to simplify the configuration, you can setup a shortcut.

```
podop = socketmap:unix:/tmp/podop.socket
virtual_alias_maps = ${podop}:alias
virtual_mailbox_domains = ${podop}:domain
virtual_mailbox_maps = ${podop}:alias
```

Dovecot usage
=============

In order to access Podop tables from Dovecot, you should setup a ``proxy``
Dovecot dictionary. For instance, in order to access the ``test`` table on
a Podop socket at ``/tmp/podop.socket``, use the following setup:

```
mail_attribute_dict = proxy:/tmp/podop.socket:test
```

Multiple maps or identical maps can be configured for various usages.

```
mail_attribute_dict = proxy:/tmp/podop.socket:meta

passdb {
  driver = dict
  args = /etc/dovecot/auth.conf
}

userdb {
  driver = dict
  args = /etc/dovecot/auth.conf
}

# then in auth.conf
uri = proxy:/tmp/podop.socket:auth
iterate_disable = yes
default_pass_scheme = plain
password_key = passdb/%u
user_key = userdb/%u
```

Contributing
============

Podop is free software, open to suggestions and contributions. All
components are free software and compatible with the MIT license. All
the code is placed under the MIT license.
