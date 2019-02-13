Mailu command line
==================

Managing users and aliases can be done from CLI using commands:

* alias
* alias-delete
* user
* user-import
* user-delete
* config-update

alias
-----

.. code-block:: bash

  docker-compose exec admin flask mailu alias foo example.net "mail1@example.com,mail2@example.com"


alias-delete
------------

.. code-block:: bash

  docker-compose exec admin flask mailu alias-delete foo@example.net

user
----

.. code-block:: bash

  docker-compose exec admin flask mailu user --hash_scheme='SHA512-CRYPT' myuser example.net 'password123'

user-import
-----------

primary difference with simple `user` command is that password is being imported as a hash - very useful when migrating users from other systems where only hash is known.

.. code-block:: bash

  docker-compose run --rm admin flask mailu user-import myuser example.net '$6$51ebe0cb9f1dab48effa2a0ad8660cb489b445936b9ffd812a0b8f46bca66dd549fea530ce' 'SHA512-CRYPT'

user-delete
------------

.. code-block:: bash

  docker-compose exec admin flask mailu user-delete foo@example.net

config-update
-------------

The sole purpose of this command is for importing users/aliases in bulk and synchronizing DB entries with external YAML template:

.. code-block:: bash

  cat mail-config.yml | docker-compose exec admin flask mailu config-update --delete_objects

where mail-config.yml looks like:

.. code-block:: bash

  users:
    - localpart: foo
      domain: example.com
      password_hash: klkjhumnzxcjkajahsdqweqqwr
      hash_scheme: MD5-CRYPT

  aliases:
    - localpart: alias1
      domain: example.com
      destination: "user1@example.com,user2@example.com"

without ``--delete_object`` option config-update will only add/update new values but will *not* remove any entries missing in provided YAML input.

Users
-----

following are additional parameters that could be defined for users:

* comment
* quota_bytes
* global_admin
* enable_imap
* enable_pop
* forward_enabled
* forward_destination
* reply_enabled
* reply_subject
* reply_body
* displayed_name
* spam_enabled
* spam_threshold

Alias
-----

additional fields:

* wildcard
