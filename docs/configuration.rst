Configuration reference
=======================

This page explains the variables found in ``mailu.env``.
In most cases ``mailu.env`` is setup correctly by the setup utility and can be left as-is.
However, some advanced settings or modifications can be done by modifying this file.

.. _common_cfg:

Common configuration
--------------------

The ``SECRET_KEY`` **must** be changed for every setup and set to a 16 bytes
randomly generated value. It is intended to secure authentication cookies
among other critical uses. This can be generated with a utility such as *pwgen*,
which can be installed on most Linux systems:

.. code-block:: bash

  apt-get install pwgen
  pwgen 16 1

The ``DOMAIN`` holds the main e-mail domain for the server. This email domain
is used for bounce emails, for generating the postmaster email and other
technical addresses.

The ``HOSTNAMES`` are all public hostnames for the mail server. Mailu supports
a mail server with multiple hostnames. The first declared hostname is the main
hostname and will be exposed over SMTP, IMAP, etc.

The ``SUBNET`` defines the address range of the docker network used by Mailu.
This should not conflict with any networks to which your system is connected.
(Internal and external!). Normally this does not need to be changed,
unless there is a conflict with existing networks.

The ``POSTMASTER`` is the local part of the postmaster email address. It is
recommended to setup a generic value and later configure a mail alias for that
address.

The ``AUTH_RATELIMIT`` holds a security setting for fighting attackers that
try to guess user passwords. The value is the limit of failed authentication attempts
that a single IP address can perform against IMAP, POP and SMTP authentication endpoints.

If ``AUTH_RATELIMIT_SUBNET`` is ``True`` (which is the default), the ``AUTH_RATELIMIT``
rules does also apply to auth requests coming from ``SUBNET``, especially for the webmail.
If you disable this, ensure that the rate limit on the webmail is enforced in a different
way (e.g. roundcube plug-in), otherwise an attacker can simply bypass the limit using webmail.


The ``TLS_FLAVOR`` sets how Mailu handles TLS connections. Setting this value to
``notls`` will cause Mailu not to server any web content! More on :ref:`tls_flavor`.

Mail settings
-------------

The ``MESSAGE_SIZE_LIMIT`` is the maximum size of a single email. It should not
be too low to avoid dropping legitimate emails and should not be too high to
avoid filling the disks with large junk emails.

The ``RELAYNETS`` are network addresses for which mail is relayed for free with
no authentication required. This should be used with great care. If you want other
Docker services' outbound mail to be relayed, you can set this to ``172.16.0.0/12``
to include **all** Docker networks. The default is to leave this empty.

The ``RELAYHOST`` is an optional address of a mail server relaying all outgoing
mail in following format: ``[HOST]:PORT``.
``RELAYUSER`` and ``RELAYPASSWORD`` can be used when authentication is needed.

The ``FETCHMAIL_DELAY`` is a delay (in seconds) for the fetchmail service to
go and fetch new email if available. Do not use too short delays if you do not
want to be blacklisted by external services, but not too long delays if you
want to receive your email in time.

The ``RECIPIENT_DELIMITED`` is a character used to delimit localpart from a
custom address part. For instance, if set to ``+``, users can use addresses
like ``localpart+custom@domain.tld`` to deliver mail to ``localpart@domain.tld``.
This is useful to provide external parties with different email addresses and
later classify incoming mail based on the custom part.

The ``DMARC_RUA`` and ``DMARC_RUF`` are DMARC protocol specific values. They hold
the localpart for DMARC rua and ruf email addresses.

Web settings
------------

The ``WEB_ADMIN`` contains the path to the main admin interface, while
``WEB_WEBMAIL`` contains the path to the Web email client.
The ``WEBROOT_REDIRECT`` redirects all non-found queries to the set path.
An empty ``WEBROOT_REDIRECT`` value disables redirecting and enables classic
behavior of a 404 result when not found.
All three options need a leading slash (``/``) to work.

  .. note:: ``WEBROOT_REDIRECT`` has to point to a valid path on the webserver.
    This means it cannot point to any services which are not enabled.
    For example, don't point it to ``/webmail`` when ``WEBMAIL=none``

Both ``SITENAME`` and ``WEBSITE`` are customization options for the panel menu
in the admin interface, while ``SITENAME`` is a customization option for
every Web interface.

.. _admin_account:

Admin account - automatic creation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
For administrative tasks, an admin user account will be needed. You can create it manually,
after deploying the system, or automatically.
To create it manually, follow the specific deployment method documentation.

To have the account created automatically, you just need to define a few environment variables:

.. code-block:: bash

  INITIAL_ADMIN_ACCOUNT = ``root`` The first part of the e-mail address (ROOT@example.com)
  INITIAL_ADMIN_DOMAIN = ``example.com`` the domain appendix. Most probably identical to the DOMAIN variable
  INITIAL_ADMIN_PW = ``password`` the chosen password for the user

Also, environment variable ``INITIAL_ADMIN_MODE`` defines how the code should behave when it will
try to create the admin user:

- ``create`` (default) Will try to create user and will raise an exception if present
- ``ifmissing``: if user exists, nothing happens, else it will be created
- ``update``: user is created or, if it exists, its password gets updated

Depending on your particular deployment you most probably will want to change the default.

Advanced settings
-----------------

The ``PASSWORD_SCHEME`` is the password encryption scheme. You should use the
default value, unless you are importing password from a separate system and
want to keep using the old password encryption scheme.

The ``LOG_LEVEL`` setting is used by the python start-up scripts as a logging threshold.
Log messages equal or higher than this priority will be printed.
Can be one of: CRITICAL, ERROR, WARNING, INFO, DEBUG or NOTSET.
See the `python docs`_ for more information.

.. _`python docs`: https://docs.python.org/3.6/library/logging.html#logging-levels

Antivirus settings
------------------

The ``ANTIVIRUS_ACTION`` switches behaviour if a virus is detected. It defaults to 'discard',
so any detected virus is silently discarded. If set to 'reject', rspamd is configured to reject
virus mails during SMTP dialogue, so the sender will receive a reject message.

Infrastructure settings
-----------------------

Various environment variables ``HOST_*`` can be used to run Mailu containers
separately from a supported orchestrator. It is used by the various components
to find the location of the other containers it depends on. They can contain an
optional port number. Those variables are:

- ``HOST_IMAP``: the container that is running the IMAP server (default: ``imap``, port 143)
- ``HOST_LMTP``: the container that is running the LMTP server (default: ``imap:2525``)
- ``HOST_HOSTIMAP``: the container that is running the IMAP server for the webmail (default: ``imap``, port 10143)
- ``HOST_POP3``: the container that is running the POP3 server (default: ``imap``, port 110)
- ``HOST_SMTP``: the container that is running the SMTP server (default: ``smtp``, port 25)
- ``HOST_AUTHSMTP``: the container that is running the authenticated SMTP server for the webnmail (default: ``smtp``, port 10025)
- ``HOST_ADMIN``: the container that is running the admin interface (default: ``admin``)
- ``HOST_ANTISPAM_MILTER``: the container that is running the antispam milter service (default: ``antispam:11332``)
- ``HOST_ANTISPAM_WEBUI``: the container that is running the antispam webui service (default: ``antispam:11334``)
- ``HOST_ANTIVIRUS``: the container that is running the antivirus service (default: ``antivirus:3310``)
- ``HOST_WEBMAIL``: the container that is running the webmail (default: ``webmail``)
- ``HOST_WEBDAV``: the container that is running the webdav server (default: ``webdav:5232``)
- ``HOST_REDIS``: the container that is running the redis daemon (default: ``redis``)
- ``HOST_WEBMAIL``: the container that is running the webmail (default: ``webmail``)

The startup scripts will resolve ``HOST_*`` to their IP addresses and store the result in ``*_ADDRESS`` for further use.

Alternatively, ``*_ADDRESS`` can directly be set. In this case, the values of ``*_ADDRESS`` is kept and not
resolved. This can be used to rely on DNS based service discovery with changing services IP addresses.
When using ``*_ADDRESS``, the hostnames must be full-qualified hostnames. Otherwise nginx will not be able to
resolve the hostnames.


