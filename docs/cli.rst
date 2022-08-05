Mailu command line
==================

Managing users and aliases can be done from CLI using commands:

* alias
* alias-delete
* domain
* password
* user
* user-import
* user-delete
* config-update
* config-export
* config-import

alias
-----

.. code-block:: bash

  docker-compose exec admin flask mailu alias foo example.net "mail1@example.com,mail2@example.com"


alias-delete
------------

.. code-block:: bash

  docker-compose exec admin flask mailu alias-delete foo@example.net


domain
------

.. code-block:: bash

  docker-compose exec admin flask mailu domain example.net


password
--------

.. code-block:: bash

  docker-compose exec admin flask mailu password myuser example.net 'password123'


user
----

.. code-block:: bash

  docker-compose exec admin flask mailu user myuser example.net 'password123'


user-import
-----------

primary difference with simple `user` command is that password is being imported as a hash - very useful when migrating users from other systems where only hash is known.

.. code-block:: bash

  docker-compose run --rm admin flask mailu user-import myuser example.net '$6$51ebe0cb9f1dab48effa2a0ad8660cb489b445936b9ffd812a0b8f46bca66dd549fea530ce' 'SHA512-CRYPT'

user-delete
-----------

.. code-block:: bash

  docker-compose exec admin flask mailu user-delete foo@example.net

config-update
-------------

The sole purpose of this command is for importing users/aliases in bulk and synchronizing DB entries with external YAML template:

.. code-block:: bash

  cat mail-config.yml | docker-compose exec -T admin flask mailu config-update --delete-objects

where mail-config.yml looks like:

.. code-block:: bash

  users:
    - localpart: foo
      domain: example.com
      password_hash: klkjhumnzxcjkajahsdqweqqwr

  aliases:
    - localpart: alias1
      domain: example.com
      destination: "user1@example.com,user2@example.com"

without ``--delete-object`` option config-update will only add/update new values but will *not* remove any entries missing in provided YAML input.

Users
^^^^^

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
* spam_mark_as_read
* spam_threshold

Alias
^^^^^

additional fields:

* wildcard

.. _config-export:

config-export
-------------

The purpose of this command is to export the complete configuration in YAML or JSON format.

.. code-block:: bash

  $ docker-compose exec admin flask mailu config-export --help

 Usage: flask mailu config-export [OPTIONS] [FILTER]...

   Export configuration as YAML or JSON to stdout or file

 Options:
   -f, --full                  Include attributes with default value.
   -s, --secrets               Include secret attributes (dkim-key, passwords).
   -d, --dns                   Include dns records.
   -c, --color                 Force colorized output.
   -o, --output-file FILENAME  Save configuration to file.
   -j, --json                  Export configuration in json format.
   -?, -h, --help              Show this message and exit.

Only non-default attributes are exported. If you want to export all attributes use ``--full``.
If you want to export plain-text secrets (dkim-keys, passwords) you have to add the ``--secrets`` option.
To include dns records (mx, spf, dkim and dmarc) add the ``--dns`` option.

By default all configuration objects are exported (domain, user, alias, relay). You can specify
filters to export only some objects or attributes (try: ``user`` or ``domain.name``).
Attributes explicitly specified in filters are automatically exported: there is no need to add ``--secrets`` or ``--full``.

.. code-block:: bash

  $ docker-compose exec admin flask mailu config-export --output mail-config.yml

  $ docker-compose exec admin flask mailu config-export domain.dns_mx domain.dns_spf

  $ docker-compose exec admin flask mailu config-export user.spam_threshold

config-import
-------------

This command imports configuration data from an external YAML or JSON source.

.. code-block:: bash

  $ docker-compose exec admin flask mailu config-import --help

 Usage: flask mailu config-import [OPTIONS] [FILENAME|-]

   Import configuration as YAML or JSON from stdin or file

 Options:
   -v, --verbose   Increase verbosity.
   -s, --secrets   Show secret attributes in messages.
   -q, --quiet     Quiet mode - only show errors.
   -c, --color     Force colorized output.
   -u, --update    Update mode - merge input with existing config.
   -n, --dry-run   Perform a trial run with no changes made.
   -?, -h, --help  Show this message and exit.

The current version of docker-compose exec does not pass stdin correctly, so you have to user docker exec instead:

.. code-block:: bash

  docker exec -i $(docker-compose ps -q admin) flask mailu config-import -nv < mail-config.yml

mail-config.yml contains the configuration and looks like this:

.. code-block:: yaml

  domain:
    - name: example.com
      alternatives:
        - alternative.example.com

  user:
    - email: foo@example.com
      password_hash: '$2b$12$...'
      hash_scheme: MD5-CRYPT

  alias:
    - email: alias1@example.com
      destination:
        - user1@example.com
        - user2@example.com

  relay:
    - name: relay.example.com
      comment: test
      smtp: mx.example.com

config-import shows the number of created/modified/deleted objects after import.
To suppress all messages except error messages use ``--quiet``.
By adding the ``--verbose`` switch the import gets more detailed and shows exactly what attributes changed.
In all log messages plain-text secrets (dkim-keys, passwords) are hidden by default. Use ``--secrets`` to log secrets.
If you want to test what would be done when importing without committing any changes, use ``--dry-run``.

By default config-import replaces the whole configuration. ``--update`` allows to modify the existing configuration instead.
New elements will be added and existing elements will be modified.
It is possible to delete a single element or prune all elements from lists and associative arrays using a special notation:

+-----------------------------+------------------+--------------------------+
| Delete what?                | notation         | example                  |
+=============================+==================+==========================+
| specific array object       | ``- -key: id``   | ``- -name: example.com`` |
+-----------------------------+------------------+--------------------------+
| specific list item          | ``- -id``        | ``- -user1@example.com`` |
+-----------------------------+------------------+--------------------------+
| all remaining array objects | ``- -key: null`` | ``- -email: null``       |
+-----------------------------+------------------+--------------------------+
| all remaining list items    | ``- -prune-``    | ``- -prune-``            |
+-----------------------------+------------------+--------------------------+

The ``-key: null`` notation can also be used to reset an attribute to its default.
To reset *spam_threshold* to it's default *80* use ``-spam_threshold: null``.

A new dkim key can be generated when adding or modifying a domain, by using the special value
``dkim_key: -generate-``.

This is a complete YAML template with all additional parameters that can be defined:

.. code-block:: yaml

  domain:
    - name: example.com
      alternatives:
        - alternative.tld
      comment: ''
      dkim_key: ''
      max_aliases: -1
      max_quota_bytes: 0
      max_users: -1
      signup_enabled: false

  user:
    - email: postmaster@example.com
      comment: ''
      displayed_name: 'Postmaster'
      enable_imap: true
      enable_pop: false
      enabled: true
      fetches:
        - id: 1
          comment: 'test fetch'
          error: null
          host: other.example.com
          keep: true
          last_check: '2020-12-29T17:09:48.200179'
          password: 'secret'
          hash_password: true
          port: 993
          protocol: imap
          tls: true
          username: fetch-user
      forward_destination:
        - address@remote.example.com
      forward_enabled: true
      forward_keep: true
      global_admin: true
      manager_of:
        - example.com
      password: '$2b$12$...'
      hash_password: true
      quota_bytes: 1000000000
      reply_body: ''
      reply_enabled: false
      reply_enddate: '2999-12-31'
      reply_startdate: '1900-01-01'
      reply_subject: ''
      spam_enabled: true
      spam_mark_as_read: true
      spam_threshold: 80
      tokens:
        - id: 1
          comment: email-client
          ip: 192.168.1.1
          password: '$5$rounds=1$...'

  alias:
    - email: email@example.com
      comment: ''
      destination:
        - address@example.com
      wildcard: false

  relay:
    - name: relay.example.com
      comment: ''
      smtp: mx.example.com
