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
* config-dump
* config-update

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

config-dump
-----------

The purpose of this command is to dump domain-, relay-, alias- and user-configuration to a YAML template.

.. code-block:: bash

  # docker-compose exec admin flask mailu config-dump --help

  Usage: flask mailu config-dump [OPTIONS] [SECTIONS]...

    dump configuration as YAML-formatted data to stdout

    SECTIONS can be: domains, relays, users, aliases

  Options:
    -f, --full     Include default attributes
    -s, --secrets  Include secrets (dkim-key, plain-text / not hashed)
    -d, --dns      Include dns records
    --help         Show this message and exit.

If you want to export secrets (dkim-keys, plain-text / not hashed) you have to add the ``--secrets`` option.
Only non-default attributes are dumped. If you want to dump all attributes use ``--full``.
To include dns records (mx, spf, dkim and dmarc) add the ``--dns`` option.
Unless you specify some sections all sections are dumped by default.

.. code-block:: bash

  docker-compose exec admin flask mailu config-dump > mail-config.yml

  docker-compose exec admin flask mailu config-dump --dns domains

config-update
-------------

The purpose of this command is for importing domain-, relay-, alias- and user-configuration in bulk and synchronizing DB entries with an external YAML template.

.. code-block:: bash

  # docker-compose exec admin flask mailu config-update --help

  Usage: flask mailu config-update [OPTIONS]

    sync configuration with data from YAML-formatted stdin

  Options:
    -v, --verbose         Increase verbosity
    -d, --delete-objects  Remove objects not included in yaml
    -n, --dry-run         Perform a trial run with no changes made
    --help                Show this message and exit.


The current version of docker-compose exec does not pass stdin correctly, so you have to user docker exec instead:

.. code-block:: bash

  docker exec -i $(docker-compose ps -q admin) flask mailu config-update -nvd < mail-config.yml


mail-config.yml looks like this:

.. code-block:: yaml
 
  domains:
    - name: example.com
      alternatives:
        - alternative.example.com

  users:
    - email: foo@example.com
      password_hash: klkjhumnzxcjkajahsdqweqqwr
      hash_scheme: MD5-CRYPT

  aliases:
    - email: alias1@example.com
      destination: "user1@example.com,user2@example.com"

  relays:
    - name: relay.example.com
      comment: test
      smtp: mx.example.com

You can use ``--dry-run`` to test your YAML without comitting any changes to the database.
With ``--verbose`` config-update will show exactly what it changes in the database.
Without ``--delete-object`` option config-update will only add/update changed values but will *not* remove any entries missing in provided YAML input.

This is a complete YAML template with all additional parameters that could be defined:

.. code-block:: yaml

  aliases:
    - email: email@example.com
      comment: ''
      destination:
        - address@example.com
      wildcard: false
  
  domains:
    - name: example.com
      alternatives:
        - alternative.tld
      comment: ''
      dkim_key: ''
      max_aliases: -1
      max_quota_bytes: 0
      max_users: -1
      signup_enabled: false
  
  relays:
    - name: relay.example.com
      comment: ''
      smtp: mx.example.com
  
  users:
    - email: postmaster@example.com
      comment: ''
      displayed_name: 'Postmaster'
      enable_imap: true
      enable_pop: false
      enabled: true
      fetches:
        - id: 1
          comment: 'test fetch'
          username: fetch-user
          host: other.example.com
          password: 'secret'
          port: 993
          protocol: imap
          tls: true
          keep: true
      forward_destination:
        - address@remote.example.com
      forward_enabled: true
      forward_keep: true
      global_admin: true
      manager_of:
        - example.com
      password: '{BLF-CRYPT}$2b$12$...'
      quota_bytes: 1000000000
      reply_body: ''
      reply_enabled: false
      reply_enddate: 2999-12-31
      reply_startdate: 1900-01-01
      reply_subject: ''
      spam_enabled: true
      spam_threshold: 80
      tokens:
        - id: 1
          comment: email-client
          ip: 192.168.1.1
          password: '$5$rounds=1000$...'

