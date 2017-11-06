Docker Compose setup
====================

Prepare the environment
-----------------------

Mailu will store all of its persistent data in a path of your choice
(``/mailu`` by default) simply create the directory and move there:

.. code-block:: bash

  mkdir /mailu
  cd /mailu

Download the initial configuration file
---------------------------------------

Docker Compose configuration is stored in a file named
:download:`docker-compose.yml`. Additionally, Mailu
relies on a :download:`.env` file for various settings. Download
the proper template files from the git repository. To download the configuration
for the ``{{ github_version }}`` branch, use:

.. code-block:: bash

  wget https://mailu.io/{{ github_version }}/_downloads/docker-compose.yml
  wget https://mailu.io/{{ github_version }}/_downloads/.env

Then open the ``.env`` file to setup the mail server. Modify the ``ROOT`` setting
to match your setup directory if different from ``/mailu``.

Mdify the ``VERSION`` configuration in the ``.env`` file to reflect the version you picked.

Set the common configuration values
-----------------------------------

Open the ``.env`` file and set configuration settings after reading the configuration
documentation. Some settings are specific to the Docker Compose setup.

Modify ``BIND_ADDRESS4`` to match the public IP address assigned to your server.
This address should be configured on one of the network interfaces of the server.
If the address is not configured directly (NAT) on any of the network interfaces or if
you would simply like the server to listen on all interfaces, use ``0.0.0.0``.

Modify ``BIND_ADDRESS6`` to match the public IPv6 address assigned to your server.
The behavior is identical to ``BIND_ADDRESS4``.

Set the ``TLS_FLAVOR`` to one of the following
values:
- ``cert`` is the default and requires certificates to be setup manually;
- ``letsencrypt`` will use the Letsencrypt! CA to generate automatic ceriticates;
- ``notls`` will disable TLS, this is not recommended except for testing.

Enable optional features
------------------------

Some of Mailu features are not used by every user and are thus not enabled in a
default configuration.

A Webmail is a Web interface exposing an email client. Mailu webmails are
bound to the internal IMAP and SMTP server for users to access their mailbox through
the Web. By exposing a complex application such as a Webmail, you should be aware of
the security implications such an increase of attack surface. The ``WEBMAIL``
configuration option must be one of the following:

- ``none`` is the default value, no Webmail service will be exposed;
- ``roundcube`` will run the popular Roundcube Webmail ;
- ``rainloop`` will run the popular Rainloop Webmail.

The administration interface is not exposed on the public address by default,
you will need to set the ``EXPOSE_ADMIN`` variable accordingly:

- ``yes`` will expose the admin interface in ``/admin``;
- ``no`` (or any other value) will disable this behaviour.

A Webdav server exposes a Dav interface over HTTP so that clients can store
contacts or calendars using the mail account. This can be enabled using the `WEBDAV`
setting. The configuration option must be one of the following:

- ``none`` is the default value, no webdav service will be exposed;
- ``radicale`` exposes the radicale Webdav service.

An antivirus server helps fighting large scale virus spreading campaigns
that leverage e-mail for initial infection. This can be setup using the ``ANTIVIRUS``
setting. The configuration option must be one of the following:

- ``none`` disables antivirus checks;
- ``clamav`` is the default values, the popular ClamAV antivirus is enabled.

Make sure that you have at least 1GB or memory for ClamAV to load its signature
database.

Finish setting up TLS
---------------------

Mailu relies heavily on TLS and must have a key pair and a certificate
available, at least for the hostname configured in the ``.env`` file.

If you set ``TLS_FLAVOR`` to ``cert`` or if then you must create a ``certs`` directory
in your root path and setup a key-certificate pair there:
- ``cert.pem`` contains the certificate,
- ``key.pem`` contains the key pair.

Start Mailu
-----------

You may now start Mailu. Move the to the Mailu directory and run:

.. code-block:: bash

  docker-compose up -d

Finally, you must create the initial admin user account:

.. code-block:: bash

  docker-compose run --rm admin python manage.py admin root example.net password

This will create a user named ``root@example.net`` with password ``password`` and administration privileges. Connect to the Web admin interface and change the password to a strong one.
