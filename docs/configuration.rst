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

The ``WILDCARD_SENDERS`` setting is a comma delimited list of user email addresses 
that are allowed to send emails from any existing address (spoofing the sender).

The ``AUTH_RATELIMIT_IP`` (default: 60/hour) holds a security setting for fighting
attackers that waste server resources by trying to guess user passwords (typically
using a password spraying attack). The value defines the limit of authentication
attempts that will be processed on non-existing accounts for a specific IP subnet
(as defined in ``AUTH_RATELIMIT_IP_V4_MASK`` and ``AUTH_RATELIMIT_IP_V6_MASK`` below).

The ``AUTH_RATELIMIT_USER`` (default: 100/day) holds a security setting for fighting
attackers that attempt to guess a user's password (typically using a password
bruteforce attack). The value defines the limit of authentication attempts allowed
for any given account within a specific timeframe.

The ``AUTH_RATELIMIT_EXEMPTION_LENGTH`` (default: 86400) is the number of seconds
after a successful login for which a specific IP address is exempted from rate limits.
This ensures that users behind a NAT don't get locked out when a single client is
misconfigured... but also potentially allow for users to attack each-other.

The ``AUTH_RATELIMIT_EXEMPTION`` (default: '') is a comma separated list of network
CIDRs that won't be subject to any form of rate limiting. Specifying ``0.0.0.0/0, ::/0``
there is a good way to disable rate limiting altogether.

The ``TLS_FLAVOR`` sets how Mailu handles TLS connections. Setting this value to
``notls`` will cause Mailu not to serve any web content! More on :ref:`tls_flavor`.

The ``DEFAULT_SPAM_THRESHOLD`` (default: 80) is the default spam tolerance used when creating a new user.

Mail settings
-------------

The ``MESSAGE_SIZE_LIMIT`` is the maximum size of a single email. It should not
be too low to avoid dropping legitimate emails and should not be too high to
avoid filling the disks with large junk emails.

The ``MESSAGE_RATELIMIT`` (default: 200/day) is the maximum number of messages
a single user can send. ``MESSAGE_RATELIMIT_EXEMPTION`` contains a comma delimited
list of user email addresses that are exempted from any restriction.  Those
settings are meant to reduce outbound spam in case of compromised or malicious
account on the server.

The ``RELAYNETS`` (default: unset) is a comma delimited list of network addresses
for which mail is relayed for with no authentication required. This should be
used with great care as misconfigurations may turn your Mailu instance into an
open-relay!

The ``RELAYHOST`` is an optional address to use as a smarthost for all outgoing
mail in following format: ``[HOST]:PORT``. ``RELAYUSER`` and ``RELAYPASSWORD``
can be used when authentication is required.

By default postfix uses "opportunistic TLS" for outbound mail. This can be changed
by setting ``OUTBOUND_TLS_LEVEL`` to ``encrypt`` or ``secure``. This setting is
highly recommended if you are using a relayhost that supports TLS but discouraged
otherwise. ``DEFER_ON_TLS_ERROR`` (default: True) controls whether incomplete
policies (DANE without DNSSEC or "testing" MTA-STS policies) will be taken into
account and whether emails will be deferred if the additional checks enforced by
those policies fail.

Similarly by default nginx uses "opportunistic TLS" for inbound mail. This can be changed
by setting ``INBOUND_TLS_ENFORCE`` to ``True``. Please note that this is forbidden for
internet facing hosts according to e.g. `RFC 3207`_ , because this prevents MTAs without STARTTLS
support or e.g. mismatching TLS versions to deliver emails to Mailu.

The ``SCAN_MACROS`` (default: True) setting controls whether Mailu will endavour
to reject emails containing documents with malicious macros. Under the hood, it uses
`mraptor from oletools`_ to determine whether a macro is malicious or not.

.. _`mraptor from oletools`: https://github.com/decalage2/oletools/wiki/mraptor

.. _`RFC 3207`: https://tools.ietf.org/html/rfc3207

.. _fetchmail:

When ``FETCHMAIL_ENABLED`` is set to ``True``, the fetchmail functionality is enabled in the admin interface.
The container itself still needs to be deployed manually. ``FETCHMAIL_ENABLED`` defaults to ``True``.

The ``FETCHMAIL_DELAY`` is a delay (in seconds) for the fetchmail service to
go and fetch new email if available. Do not use too short delays if you do not
want to be blacklisted by external services, but not too long delays if you
want to receive your email in time.

The ``RECIPIENT_DELIMITER`` is a list of characters used to delimit localpart
from a custom address part. For instance, if set to ``+-``, users can use
addresses like ``localpart+custom@example.com`` or ``localpart-custom@example.com``
to deliver mail to ``localpart@example.com``.
This is useful to provide external parties with different email addresses and
later classify incoming mail based on the custom part.

The ``DMARC_RUA`` and ``DMARC_RUF`` are DMARC protocol specific values. They hold
the localpart for DMARC rua and ruf email addresses.

Full-text search is enabled for IMAP is enabled by default. This feature can be disabled
(e.g. for performance reasons) by setting the optional variable ``FULL_TEXT_SEARCH`` to ``off``.

.. _web_settings:

Web settings
------------

- ``WEB_ADMIN`` contains the path to the main admin interface

- ``WEB_WEBMAIL`` contains the path to the Web email client.

- ``WEBROOT_REDIRECT`` redirects all non-found queries to the set path.
  An empty ``WEBROOT_REDIRECT`` value disables redirecting and enables 
  classic behavior of a 404 result when not found.
  Alternatively, ``WEBROOT_REDIRECT`` can be set to ``none`` if you 
  are using an Nginx override for ``location /``.

All three options need a leading slash (``/``) to work.

  .. note:: ``WEBROOT_REDIRECT`` has to point to a valid path on the webserver.
    This means it cannot point to any services which are not enabled.
    For example, don't point it to ``/webmail`` when ``WEBMAIL=none``

Both ``SITENAME`` and ``WEBSITE`` are customization options for the panel menu
in the admin interface, while ``SITENAME`` is a customization option for
every Web interface.

- ``LOGO_BACKGROUND`` sets a custom background colour for the brand logo 
  in the top left of the main admin interface.
  For a list of colour codes refer to this page of `w3schools`_.

- ``LOGO_URL`` sets a URL for a custom logo. This logo replaces the Mailu 
  logo in the topleft of the main admin interface.

.. _`w3schools`: https://www.w3schools.com/cssref/css_colors.asp

.. _admin_account:

Admin account - automatic creation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
For administrative tasks, an admin user account will be needed. You can create it manually,
after deploying the system, or automatically.
To create it manually, follow the specific deployment method documentation.

To have the account created automatically, you just need to define a few environment variables:

- ``INITIAL_ADMIN_ACCOUNT``: the admin username: The first part of the e-mail address before the @.
- ``INITIAL_ADMIN_DOMAIN``: the domain appendix: Most probably identical to the ``DOMAIN`` variable.
- ``INITIAL_ADMIN_PW``: the admin password.
- ``INITIAL_ADMIN_MODE``: use one of the options below for configuring how the admin account must be created:

  - ``create``: (default) creates a new admin account and raises an exception when it already exists.
  - ``ifmissing``: creates a new admin account when the admin account does not exist.
  - ``update``: creates a new admin account when it does not exist, or update the password of an existing admin account.

Note: It is recommended to set ``INITIAL_ADMIN_MODE`` to either ``update`` or ``ifmissing``. Leaving it with the 
default value will cause an error when the system is restarted.

An example:

.. code-block:: bash

  INITIAL_ADMIN_ACCOUNT=me
  INITIAL_ADMIN_DOMAIN=example.net
  INITIAL_ADMIN_PW=password
  INITIAL_ADMIN_MODE=ifmissing

Depending on your particular deployment you most probably will want to change the default.

.. _advanced_cfg:

Advanced settings
-----------------

The ``CREDENTIAL_ROUNDS`` (default: 12) setting is the number of rounds used by the 
password hashing scheme. The number of rounds can be reduced in case faster 
authentication is needed or increased when additional protection is desired. 
Keep in mind that this is a mitigation against offline attacks on password hashes, 
aiming to prevent credential stuffing (due to password re-use) on other systems.

The ``SESSION_COOKIE_SECURE`` (default: True) setting controls the secure flag on 
the cookies of the administrative interface. It should only be turned off if you 
intend to access it over plain HTTP.

``SESSION_TIMEOUT`` (default: 3600) is the maximum amount of time in seconds between 
requests before a session is invalidated. ``PERMANENT_SESSION_LIFETIME`` (default: 108000) 
is the maximum amount of time in seconds a session can be kept alive for if it hasn't timed-out.

The ``LOG_LEVEL`` setting is used by the python start-up scripts as a logging threshold.
Log messages equal or higher than this priority will be printed.
Can be one of: CRITICAL, ERROR, WARNING, INFO, DEBUG or NOTSET.
See the `python docs`_ for more information.

.. _`python docs`: https://docs.python.org/3.6/library/logging.html#logging-levels

The ``LETSENCRYPT_SHORTCHAIN`` (default: False) setting controls whether we send the 
ISRG Root X1 certificate in TLS handshakes. This is required for `android handsets older than 7.1.1` 
but slows down the performance of modern devices.

.. _`android handsets older than 7.1.1`: https://community.letsencrypt.org/t/production-chain-changes/150739

The ``TLS_PERMISSIVE`` (default: true) setting controls whether ciphers and protocols offered on port 25 for STARTTLS are optimized for maximum compatibility. We **strongly recommend** that you do **not** change this setting on the basis that any encryption beats no encryption. If you are subject to compliance requirements and are not afraid of losing emails as a result of artificially reducing compatibility, set it to 'false'. Keep in mind that servers that are running a software stack old enough to not be compatible with the current TLS requirements will either a) deliver in plaintext b) bounce emails c) silently drop emails; moreover, modern servers will benefit from various downgrade protections (DOWNGRD, RFC7507) making the security argument mostly a moot point.

.. _reverse_proxy_headers:

The ``REAL_IP_HEADER`` (default: unset) and ``REAL_IP_FROM`` (default: unset) settings 
controls whether HTTP headers such as ``X-Forwarded-For`` or ``X-Real-IP`` should be trusted. 
The former should be the name of the HTTP header to extract the client IP address from and the 
later a comma separated list of IP addresses designating which proxies to trust. 
If you are using Mailu behind a reverse proxy, you should set both. Setting the former without 
the later introduces a security vulnerability allowing a potential attacker to spoof his source address.

The ``TZ`` sets the timezone Mailu will use. The timezone naming convention usually uses a ``Region/City`` format. See `TZ database name`_  for a list of valid timezones This defaults to ``Etc/UTC``. Warning: if you are observing different timestamps in your log files you should change your hosts timezone to UTC instead of changing TZ to your local timezone. Using UTC allows easy log correlation with remote MTAs.

.. _`TZ database name`: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

Antivirus settings
------------------

The ``ANTIVIRUS_ACTION`` switches behaviour if a virus is detected. It defaults to 'discard',
so any detected virus is silently discarded. If set to 'reject', rspamd is configured to reject
virus mails during SMTP dialogue, so the sender will receive a reject message.

Infrastructure settings
-----------------------

Various environment variables ``*_ADDRESS`` can be used to run Mailu containers
separately from a supported orchestrator. It is used by the various components
to find the location of the other containers it depends on. Those variables are:

- ``ADMIN_ADDRESS``
- ``ANTISPAM_ADDRESS``
- ``ANTIVIRUS_ADDRESS``
- ``FRONT_ADDRESS``
- ``IMAP_ADDRESS``
- ``REDIS_ADDRESS``
- ``SMTP_ADDRESS``
- ``WEBDAV_ADDRESS``
- ``WEBMAIL_ADDRESS``

These are used for DNS based service discovery with possibly changing services IP addresses.
``*_ADDRESS`` values must be fully qualified domain names without port numbers.

.. _db_settings:

Database settings
-----------------


The admin service stores configurations in a database.

- ``DB_FLAVOR``: the database type for mailu admin service. (``sqlite``, ``postgresql``, ``mysql``)
- ``DB_HOST``: the database host for mailu admin service. For non-default ports use the notation `host:port`. (when not ``sqlite``)
- ``DB_PW``: the database password for mailu admin service. (when not ``sqlite``)
- ``DB_USER``: the database user for mailu admin service. (when not ``sqlite``)
- ``DB_NAME``: the database name for mailu admin service. (when not ``sqlite``)

Alternatively, if you need more control, you can use a `DB URL`_ : do not set any of the ``DB_`` settings and set ``SQLALCHEMY_DATABASE_URI`` instead.

.. _`DB URL`: https://docs.sqlalchemy.org/en/latest/core/engines.html#database-urls

The roundcube service stores configurations in a database.

- ``ROUNDCUBE_DB_FLAVOR``: the database type for roundcube service. (``sqlite``, ``postgresql``, ``mysql``)
- ``ROUNDCUBE_DB_HOST``: the database host for roundcube service. For non-default ports use the notation `host:port`. (when not ``sqlite``)
- ``ROUNDCUBE_DB_PW``: the database password for roundcube service. (when not ``sqlite``)
- ``ROUNDCUBE_DB_USER``: the database user for roundcube service. (when not ``sqlite``)
- ``ROUNDCUBE_DB_NAME``: the database name for roundcube service. (when not ``sqlite``)

Webmail settings
----------------

When using roundcube it is possible to select the plugins to be enabled by setting ``ROUNDCUBE_PLUGINS`` to
a comma separated list of plugin-names. Included plugins are:

- acl (needs configuration)
- additional_message_headers (needs configuration)
- archive
- attachment_reminder
- carddav
- database_attachmentsi
- debug_logger
- emoticons
- enigma
- help
- hide_blockquote
- identicon
- identity_select
- jqueryui
- mailu
- managesieve
- markasjunk
- new_user_dialog
- newmail_notifier
- reconnect
- show_additional_headers (needs configuration)
- subscriptions_option
- vcard_attachments
- zipdownload

If ``ROUNDCUBE_PLUGINS`` is not set the following plugins are enabled by default:

- archive
- carddav
- enigma
- mailu
- managesieve
- markasjunk
- zipdownload

To disable all plugins just set ``ROUNDCUBE_PLUGINS`` to ``mailu``.

To configure a plugin add php files named ``*.inc.php`` to roundcube's :ref:`override section <override-label>`.

Mail log settings
-----------------

By default, all services log directly to stdout/stderr. Logs can be collected by any docker log processing solution.

Postfix writes the logs to a syslog server which logs to stdout. This is used to filter 
out messages from the healthcheck. In some situations, a separate mail log is required 
(e.g. for legal reasons). The syslog server can be configured to write log files to a volume. 
It can be configured with the following option:

- ``POSTFIX_LOG_FILE``: The file to log the mail log to. When enabled, the syslog server will also log to stdout.

When ``POSTFIX_LOG_FILE`` is enabled, the logrotate program will automatically rotate the 
logs every week and keep 52 logs. To override the logrotate configuration, create the file logrotate.conf 
with the desired configuration in the :ref:`Postfix overrides folder<override-label>`.


Header authentication using an external proxy
---------------------------------------------

The ``PROXY_AUTH_WHITELIST`` (default: unset/disabled) option allows you to configure a comma separated list of CIDRs of proxies to trust for authentication. This list is separate from ``REAL_IP_FROM`` and any entry in ``PROXY_AUTH_WHITELIST`` should also appear in ``REAL_IP_FROM``.

Use ``PROXY_AUTH_HEADER`` (default: 'X-Auth-Email') to customize which HTTP header the email address of the user to authenticate as should be and ``PROXY_AUTH_CREATE`` (default: False) to control whether non-existing accounts should be auto-created. Please note that Mailu doesn't currently support creating new users for non-existing domains; you do need to create all the domains that may be used manually.

Once configured, any request to /sso/proxy will be redirected to the webmail and /sso/proxy/admin to the admin panel. Please check issue `1972` for more details.

.. _`1972`: https://github.com/Mailu/Mailu/issues/1972
