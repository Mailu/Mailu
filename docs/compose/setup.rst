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
for the ``VERSION_TAG`` branch, use:

.. code-block:: bash

  wget https://mailu.io/VERSION_TAG/_downloads/docker-compose.yml
  wget https://mailu.io/VERSION_TAG/_downloads/.env

Important configuration variables
---------------------------------

Open the ``.env`` file and review the following variable settings:

- Change ``ROOT`` if you have your setup directory in a different location then ``/mailu``.
- Check ``VERSION`` to reflect the version you picked. (``master`` or ``1.5``).

Make sure to read the comments in the file and instructions from the :ref:`common_cfg` section.

TLS certificates
````````````````

Set the ``TLS_FLAVOR`` to one of the following
values:

- ``cert`` is the default and requires certificates to be setup manually;
- ``letsencrypt`` will use the *Letsencrypt!* CA to generate automatic ceriticates;
- ``mail`` is similar to ``cert`` except that TLS will only be served for
  emails (IMAP and SMTP), not HTTP (use it behind reverse proxies);
- ``mail-letsencrypt`` is similar to ``letsencrypt`` except that TLS will only be served for
  emails (IMAP and SMTP), not HTTP (use it behind reverse proxies);
- ``notls`` will disable TLS, this is not recommended except for testing

.. note::

  When using *Letsencrypt!* you have to make sure that the DNS ``A`` and ``AAAA`` records for the
  all hostnames mentioned in the ``HOSTNAMES`` variable match with the ip adresses of you server.
  Or else certificate generation will fail! See also: :ref:`dns_setup`.

Bind address
````````````

Modify ``BIND_ADDRESS4`` and ``BIND_ADDRESS6`` to match the public IP addresses assigned to your server. For IPv6 you will need the ``<global>`` scope address. 

You can find those addresses by running the following:

.. code-block:: bash

  [root@mailu ~]$ ifconfig eth0
  eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
          inet 125.189.138.127  netmask 255.255.255.0  broadcast 5.189.138.255
          inet6 fd21:aab2:717c:cc5a::1  prefixlen 64  scopeid 0x0<global>
          inet6 fe2f:2a73:43a8:7a1b::1  prefixlen 64  scopeid 0x20<link>
          ether 00:50:56:3c:b2:23  txqueuelen 1000  (Ethernet)
          RX packets 174866612  bytes 127773819607 (118.9 GiB)
          RX errors 0  dropped 0  overruns 0  frame 0
          TX packets 19905110  bytes 2191519656 (2.0 GiB)
          TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

If the address is not configured directly (NAT) on any of the network interfaces or if
you would simply like the server to listen on all interfaces, use ``0.0.0.0`` and ``::``. Note that running is this mode is not supported and can lead to `issues`_.

.. _issues: https://github.com/Mailu/Mailu/issues/641

Enable optional features
------------------------

Some of Mailu features are not used by every user and are thus not enabled in a
default configuration.

A Webmail is a Web interface exposing an email client. Mailu webmails are
bound to the internal IMAP and SMTP server for users to access their mailbox through
the Web. By exposing a complex application such as a Webmail, you should be aware of
the security implications caused by such an increase of attack surface. The ``WEBMAIL``
configuration option must be one of the following:

- ``none`` is the default value, no Webmail service will be exposed;
- ``roundcube`` will run the popular Roundcube Webmail;
- ``rainloop`` will run the popular Rainloop Webmail.

The administration interface is not exposed on the public address by default,
you will need to set the ``ADMIN`` variable accordingly:

- ``true`` will expose the admin interface in ``/admin``;
- ``false`` (or any other value) will disable this behaviour.

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

Make sure that you have at least 1GB of memory for ClamAV to load its signature
database.

If you run Mailu behind a reverse proxy you can use ``REAL_IP_HEADER`` and
``REAL_IP_FROM`` to set the values of respective the Nginx directives
``real_ip_header`` and ``set_real_ip_from``. The ``REAL_IP_FROM`` configuration
option is a comma-separated list of IPs (or CIDRs) of which for each a
``set_real_ip_from`` directive is added in the Nginx configuration file.

Finish setting up TLS
---------------------

Mailu relies heavily on TLS and must have a key pair and a certificate
available, at least for the hostname configured in the ``.env`` file.

If you set ``TLS_FLAVOR`` to ``cert`` or ``mail`` then you must create a ``certs`` directory
in your root path and setup a key-certificate pair there:

- ``cert.pem`` contains the certificate (override with ``TLS_CERT_FILENAME``),
- ``key.pem`` contains the key pair (override with ``TLS_KEYPAIR_FILENAME``).

Start Mailu
-----------

You may now start Mailu. Move the to the Mailu directory and run:

.. code-block:: bash

  docker-compose up -d

Finally, you must create the initial admin user account:

.. code-block:: bash

  docker-compose run --rm admin python manage.py admin root example.net password

This will create a user named ``root@example.net`` with password ``password`` and administration privileges. Connect to the Web admin interface and change the password to a strong one.
