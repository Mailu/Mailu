Configuration reference
=======================

This page explains the variables found in ``mailu.env``.
In most cases ``mailu.env`` is setup correctly by the setup utility and can be left as-is.
However, some advanced settings or modifications can be done by modifying this file.

Mail storage layout
-------------------

Dovecot stores each mailbox under ``/mail/<domain>/<shard>/<localpart>``, where
the shard is the first two lowercase base32 characters of the 2-byte BLAKE2s
digest of the full email address. Maildir messages and mailbox control state
live in ``mail/``, persistent indexes and quota state in ``indexes/``, personal
Sieve scripts and their activation link in ``sieve/``, and IMAP metadata in
``metadata/``. Dovecot keeps its index cache alongside the persistent indexes.

On upgrade, the IMAP container migrates recognized data from the previous
``/mail/<email-address>`` layout before starting Dovecot. The migration can be
restarted safely after interruption, normalizes Maildir message size fields,
and rebuilds Dovecot indexes. Unrecognized files are left in the legacy
directory for manual review. The IMAP container records the effective
full-text-search language configuration, removes stale FTS indexes when FTS is
disabled, and rebuilds them when the language choices change. Obsolete Xapian
indexes are discarded as rebuildable data and are never migrated.

To import a filesystem Maildir into an existing Mailu installation, use the
same legacy staging location, ``/mail/<email-address>``. Create the mailbox
account first so it has a Dovecot UID/GID, stop the IMAP container, copy the
contents of the Maildir root into that location, and start the IMAP container
again. The startup migration detects staged mailboxes even after the initial
layout migration has completed. It moves recognized state into the account's
new home, assigns the account's UID/GID, normalizes message sizes, and queues
index and quota rebuilding. This operation can take a long time; see
:ref:`import_external_mailbox` for the full procedure and checks.

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
hostname and will be exposed over SMTP, IMAP, etc. Requests made using a
hostname that is not configured are redirected to the main hostname. Mailu
publishes the configured HTTPS origins at
``/.well-known/webauthn`` so browsers can use passkeys on each configured
hostname. Mailu also publishes mail client configuration at
``/.well-known/client-autoconfig.xml`` and retains the legacy Thunderbird
AutoConfig URLs for older clients.

The ``SUBNET`` defines the address range of the docker network used by Mailu.
This should not conflict with any networks to which your system is connected.
(Internal and external!). Normally this does not need to be changed,
unless there is a conflict with existing networks.

The ``SUBNET6`` (default: unset) defines the IPv6 address range of the docker network used by Mailu.
It is set by the setup utility when IPv6 is enabled and should be a ULA range (``fd00::/8``).
When it is set, Mailu services listen on IPv6 addresses as well. Leave it unset to run IPv4 only.
Enabling IPv6 also requires the Docker network to have IPv6 enabled, see :doc:`faq` for details.


The ``POSTMASTER`` is the local part of the postmaster email address. It is
recommended to setup a generic value and later configure a mail alias for that
address.

The ``WILDCARD_SENDERS`` setting is a comma delimited list of user email addresses
that are allowed to send emails from any existing address (spoofing the sender).

.. _AUTH Ratelimit:

The ``AUTH_RATELIMIT_IP`` (default: 5/hour) holds a security setting for fighting
attackers that attempt a password spraying attack. The value defines the limit of
authentication attempts that will be processed on **distinct** non-existing
accounts for a specific IP subnet as defined in
``AUTH_RATELIMIT_IP_V4_MASK`` (default: /24) and
``AUTH_RATELIMIT_IP_V6_MASK`` (default: /48).

The ``AUTH_RATELIMIT_USER`` (default: 50/day) holds a security setting for fighting
attackers that attempt to guess a user's password (typically using a password
brute-force attack). The value defines the limit of distinct authentication attempts
allowed for any given account within a specific time-frame. Multiple attempts for the
same account with the same password only counts for one.

The ``AUTH_RATELIMIT_EXEMPTION_LENGTH`` (default: 86400) is the number of seconds
after a successful login for which a specific IP address is exempted from rate limits.
This ensures that users behind a NAT don't get locked out when a single client is
misconfigured... but also potentially allow for users to attack each-other.

The ``AUTH_RATELIMIT_EXEMPTION`` (default: '') is a comma separated list of network
CIDRs that won't be subject to any form of rate limiting. Specifying ``0.0.0.0/0, ::/0``
there is a good way to disable rate limiting altogether.

The ``TLS_FLAVOR`` sets how Mailu obtains a x509 certificate. More on :ref:`tls_flavor`.

The ``LETSENCRYPT_SHORTCHAIN`` setting (default: ``True``) controls the ECDSA
chain served by front TLS services when ``TLS_FLAVOR`` is ``letsencrypt`` or
``mail-letsencrypt``. Set it to ``False`` to serve Certbot's full ECDSA chain,
which includes the cross-signed ISRG Root X2 certificate for clients that only
trust ISRG Root X1. SMTP port 25 continues to use its DANE-specific chains.

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
open-relay! Make sure clients are using port 25 with no authentication.

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

The ``SCAN_MACROS`` (default: True) setting controls whether Mailu will endeavor
to reject emails containing documents with malicious macros. Under the hood, it uses
`mraptor from oletools`_ to determine whether a macro is malicious or not.

.. _`mraptor from oletools`: https://github.com/decalage2/oletools/wiki/mraptor

.. _`RFC 3207`: https://tools.ietf.org/html/rfc3207

.. _fetchmail:

When ``FETCHMAIL_ENABLED`` is set to ``True``, the fetchmail functionality is enabled and
shown in the admin interface. The container itself still needs to be deployed manually.
``FETCHMAIL_ENABLED`` defaults to ``True``.

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

``DMARC_SEND_REPORTS`` (default: false) enables automated DMARC aggregate report 
generation and sending using Rspamd 3.0+. When enabled, Mailu will automatically 
generate and send daily DMARC aggregate reports to domains that request them via 
their DMARC policy records. Reports are sent at 2 AM daily for the previous day's 
email traffic from ``POSTMASTER@DOMAIN``.

The ``FULL_TEXT_SEARCH`` variable (default: 'en') is a comma separated list of
ISO 639-1 language codes, as listed under `Dovecot languages`_. This feature can
be disabled (e.g. for performance reasons) by setting the variable to ``off``.
Legacy boolean values such as ``on``, ``true``, ``yes``, and ``1`` enable
English indexing; ``off``, ``false``, ``no``, and ``0`` disable indexing.

The domain's **Maximum user quota** sets a limit for each mailbox. **Maximum
domain storage** sets an additional best-effort limit across its mailboxes. The
Admin interface reports current aggregate usage from Dovecot's quota data, and
Postfix checks it when accepting each inbound SMTP recipient. The check uses a
usage snapshot and can be exceeded by concurrent deliveries; it does not cover
IMAP uploads or moves between mailboxes. Set the domain limit to zero for no
aggregate limit.

You can set a global ``DEFAULT_QUOTA`` to be used for mailboxes when the domain has
no specific per-user quota configured.

.. _`Dovecot languages`: https://doc.dovecot.org/latest/core/plugins/fts.html

.. _web_settings:

Web settings
------------

- ``WEBMAIL_AVAILABLE`` is a comma-separated list of enabled webmails.
  If unset or empty, both webmails are enabled. Set it to ``none`` to disable
  both webmails. If ``none`` appears in the list, it takes
  precedence over any webmail names. The webmails are served at ``/roundcube`` and ``/snappymail``;
  ``/webmail`` redirects signed-in users to their preferred enabled webmail.
  Users can select their preference in account settings. If their choice is
  disabled, the first enabled webmail is used. Restart the front and admin
  services after changing this setting.

  Both webmails run in the same webmail container and use its existing data
  directory. Replace the old ``WEBMAIL`` setting with ``WEBMAIL_AVAILABLE``
  when upgrading. Mount ``$ROOT/overrides/roundcube`` at
  ``/roundcube-overrides`` for Roundcube ``.inc`` and ``.inc.php`` files, and
  ``$ROOT/overrides/snappymail`` at ``/snappymail-overrides`` for an optional
  ``application.ini`` containing SnappyMail settings to override. Restart the
  webmail service after changing overrides. When both webmails are disabled, the default
  webmail root redirect falls back to ``/admin`` if the admin interface is
  enabled. The setup wizard can also omit the webmail service entirely.

- ``WEBROOT_REDIRECT`` redirects all non-found queries to the set path.
  An empty ``WEBROOT_REDIRECT`` value disables redirecting and enables
  classic behavior of a 404 result when not found.
  Alternatively, ``WEBROOT_REDIRECT`` can be set to ``none`` if you
  are using an Nginx override for ``location /``.

The redirect path needs a leading slash (``/``) to work.

  .. note:: ``WEBROOT_REDIRECT`` has to point to a valid path on the webserver.
    A redirect to ``/webmail`` falls back to ``/admin`` (or a 404 when admin is
    disabled) if ``WEBMAIL_AVAILABLE=none``.

Both ``SITENAME`` and ``WEBSITE`` are customization options for the panel menu
in the admin interface, while ``SITENAME`` is a customization option for
every Web interface.

- ``LOGO_BACKGROUND`` sets a custom background colour for the brand logo
  in the top-left of the main admin interface.
  For a list of colour codes refer to this page of `w3schools`_.

- ``LOGO_URL`` sets a URL for a custom logo. This logo replaces the Mailu
  logo in the top-left of the main admin interface.

.. _`w3schools`: https://www.w3schools.com/cssref/css_colors.asp

.. _admin_account:

Admin account - initial setup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
To create the first administrator, create a user and request a one-time setup link,
then promote the account to global administrator:

.. code-block:: bash

  docker compose exec admin flask mailu user add me@example.net
  docker compose exec admin flask mailu admin add me@example.net

Omitting the password creates a random password and prints a one-time setup link
in the command output. Open it to set a password or register a passkey. The link expires after the configured account setup token
lifetime and can only be used once. Keep the link private: anyone who can use it
can take control of the account.

.. _advanced_settings:

Advanced settings
-----------------


The ``AUTH_REQUIRE_TOKENS`` (default: True) setting requires email clients to authenticate using authentication tokens (application-specific passwords). Create one token per app or device and save it in the client's incoming and outgoing password fields. Web sign-in continues to support account passwords and passkeys. Installations that need legacy password authentication for email clients can explicitly set ``AUTH_REQUIRE_TOKENS=False``.

The ``API_TOKEN`` (default: None) setting configures the authentication token.
The minimum length is 3 characters.
This token must be passed as request header to the API as authentication token.
This is a mandatory setting for using the RESTful API.

The ``CREDENTIAL_ROUNDS`` (default: 13) setting is the number of rounds used by the
password hashing scheme. The number of rounds can be reduced in case faster
authentication is needed or increased when additional protection is desired.
Keep in mind that this is a mitigation against offline attacks on password hashes,
aiming to prevent credential stuffing (due to password re-use) on other systems.

The ``SESSION_COOKIE_SECURE`` (default: True) setting controls the secure flag on
the cookies of the administrative interface. It should only be turned off if you
intend to access it over plain HTTP.

The ``PASSKEY_RP_ID`` setting selects the WebAuthn relying-party ID for passkeys.
It defaults to the first hostname in ``HOSTNAMES``. Set it to the domain users
access the web interface through if that differs from the first hostname. Passkeys
require a secure browser context, normally HTTPS. When multiple hostnames are
configured, Mailu serves them as related origins for this RP ID from
``https://<PASSKEY_RP_ID>/.well-known/webauthn``.

The ``PASSKEY_REQUIRED`` setting (default: ``False``) requires every account
to use a passkey, across all domains. When enabled, password sign-in is disabled
and the login form only offers passkey sign-in. Accounts without a passkey need
a one-time account setup link from their domain administrator before they can
sign in. This is a server-wide passwordless policy.

Domain managers can instead enable **Require all users to enroll a passkey** in
the domain's passkey policy. This requires users without a passkey to set one up
after signing in, while allowing them to use their existing password to sign in.
They cannot continue to other Mailu pages until enrollment is complete. A manager
can create a one-time setup or recovery link from the user's edit page to help a
locked-out user. The link can also set or reset a password when the account is
allowed to use passwords. Global administrators can manage all domain settings; domain managers
can edit only the passkey policy. For a per-user requirement, use **Require
passkey** on the user's create or edit form; this option is hidden if
the domain already requires passkeys or the server-wide setting is enabled.

The ``ACCOUNT_SETUP_TOKEN_TTL`` setting controls how long one-time account setup
and recovery links remain valid, in seconds. It defaults to ``604800`` (one
week). A link can be used once to set a password or add a passkey, subject to
account passkey policies. Generating a replacement invalidates any previous
link for that account.

``SESSION_TIMEOUT`` (default: 3600) is the maximum amount of time in seconds between
requests before a session is invalidated. ``PERMANENT_SESSION_LIFETIME`` (default: 108000)
is the maximum amount of time in seconds a session can be kept alive for if it hasn't timed-out.

The ``LOG_LEVEL`` setting is used by the python start-up scripts as a logging threshold.
Log messages equal or higher than this priority will be printed.
Can be one of: CRITICAL, ERROR, WARNING, INFO, DEBUG or NOTSET.
See the `python docs`_ for more information.

.. _`python docs`: https://docs.python.org/3.6/library/logging.html#logging-levels

With ``TLS_FLAVOR=letsencrypt``, front TLS services offer both RSA and ECDSA
certificates. The RSA chain keeps its path through ISRG Root X1 for compatibility;
the ECDSA chain includes the Root YE certificate signed by ISRG Root X2 but
omits X2 itself. This keeps the transmitted chain ECC-only and shorter; clients
must already trust ISRG Root X2. SMTP port 25 continues to serve the RSA and
ECDSA DANE chains, including their DNS-published ISRG trust anchors.

The ``TLS_PERMISSIVE`` (default: true) setting controls whether ciphers and protocols offered on port 25
for STARTTLS are optimized for maximum compatibility. We **strongly recommend** that you do **not** change
this setting on the basis that any encryption beats no encryption. If you are subject to compliance
requirements and are not afraid of losing emails as a result of artificially reducing compatibility,
set it to 'false'. Keep in mind that servers that are running a software stack old enough to not be
compatible with the current TLS requirements will either a) deliver in plaintext b) bounce emails
c) silently drop emails; moreover, modern servers will benefit from various downgrade protections
(DOWNGRD, RFC7507) making the security argument mostly a moot point.

The ``COMPRESSION`` (default: unset) setting controls whether emails are stored compressed at rest on disk.
Valid values are ``gz``, ``bz2`` or ``zstd``. The compression strength is set with
``COMPRESSION_LEVEL``, whose meaning depends on the method: for ``gz`` it is the zlib level (0 to 9),
for ``zstd`` the zstd level, and for ``bz2`` it is the block size in units of 100k (1 to 9). See
`mail_compress`_ for details. If the underlying filesystem
supports compression natively you should use it instead of this setting as it will be more efficient
and will improve compatibility with 3rd party tools.

.. _`mail_compress`: https://doc.dovecot.org/latest/core/plugins/mail_compress.html

.. _reverse_proxy_headers:

The ``REAL_IP_HEADER`` (default: unset) and ``REAL_IP_FROM`` (default: unset) settings
control whether HTTP headers such as ``X-Forwarded-For`` or ``X-Real-IP`` should be trusted.
These settings are for HTTP-header-based proxies. For the recommended TCP reverse-proxy setup,
use ``PROXY_PROTOCOL`` and ``REAL_IP_FROM`` instead, and leave ``REAL_IP_HEADER`` unset. If your
proxy forwards client addresses in HTTP headers, set ``REAL_IP_HEADER`` to the header name and
``REAL_IP_FROM`` to a comma-separated list of trusted proxy addresses. Setting the former without
the latter introduces a security vulnerability that allows an attacker to spoof their source address.

The ``TZ`` sets the timezone Mailu will use. The timezone naming convention usually uses a ``Region/City`` format. See `TZ database name`_  for a list of valid timezones This defaults to ``Etc/UTC``. Warning: if you are observing different timestamps in your log files you should change your hosts timezone to UTC instead of changing TZ to your local timezone. Using UTC allows easy log correlation with remote MTAs.

.. _`TZ database name`: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones


The ``PORTS`` (default: '25,80,443,465,993,995,4190') setting determines which services should be enabled. It is a comma delimited list of ports numbers.
If you need to re-enable IMAP, POP3 and Submission, you can append '110,143,587' to that list. Please note that ports 25,465 and 993 cannot be disabled.

The ``PROXY_PROTOCOL`` (default: unset) setting allows the the front container to receive TCP and HTTP connections with
the `PROXY protocol`_ (originally introduced in HAProxy, now also configurable in other proxy servers).
It can be set to a comma delimited list of ports on which it should be enabled.

.. _`PROXY protocol`: https://github.com/haproxy/haproxy/blob/master/doc/proxy-protocol.txt

This requires to have a valid ``REAL_IP_FROM`` (default: unset). Setting ``PROXY_PROTOCOL`` without setting
``REAL_IP_FROM`` *will not work*. The ``REAL_IP_HEADER`` **must be unset**. Otherwise Mailu will not accept
the IP address from the remote client specified by the proxy. This results in the proxy being rate limited
or even banned (when fail2ban is used).
Make sure to set a ``REAL_IP_FROM`` only pointing to IP addresses or networks
that you trust; accepting the ``PROXY`` protocol from untrusted sources is a serious security vulnerability,
allowing a potential attacker to spoof their source address.

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

Both the admin and roundcube services store their configurations in a SQLite database.
Alternatives hosted options like PostgreSQL and MariaDB/MySQL can be configured using `DB URL`_
but the development team recommends against it. Indeed, there is currently very little data
to be stored and SQLite is deemed both sufficient, simpler and more reliable overall.

- ``SQLALCHEMY_DATABASE_URI`` (default: ``sqlite:////data/main.db``): the SQLAlchemy database URL for accessing the database
- ``SQLALCHEMY_DATABASE_URI_ROUNDCUBE`` (default: ``sqlite:////data/roundcube.db``): the Roundcube database URL for accessing the Roundcube database

For PostgreSQL use driver postgresql (``SQLALCHEMY_DATABASE_URI=postgresql://mailu:mailu_secret_password@database/mailu``).

For MariaDB/MySQL use driver mysql+mysqlconnector (``SQLALCHEMY_DATABASE_URI= mysql+mysqlconnector://mailu:mailu_secret_password@database/mailu``).

For Roundcube, refer to the `roundcube documentation`_ for the URL specification.

.. _`DB URL`: https://docs.sqlalchemy.org/en/latest/core/engines.html#database-urls
.. _`roundcube documentation`: https://github.com/roundcube/roundcubemail/blob/master/config/defaults.inc.php#L28

.. _webmail-settings:

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

With ``WEBDAV=radicale``, the default ``carddav`` plugin automatically discovers
the user's Mailu address books. SnappyMail's ``mailu-carddav`` plugin configures
CardDAV synchronization unless the user has saved their own sync settings.
Keep ``mailu-carddav`` in ``[plugins] enabled_list`` when overriding SnappyMail's
plugin list if automatic setup is wanted.

Roundcube's CardDAV plugin uses a separate ``$prefs`` configuration, rather than
Roundcube's ``$config`` array. To add server-wide presets or customize these
settings, create ``overrides/roundcube/carddav.php`` (without ``.inc`` in its
name). For example, a shared read-only address book with service credentials::

    <?php
    $prefs['Company'] = [
        'accountname' => 'Company contacts',
        'username' => 'directory-reader',
        'password' => 'external-service-app-password',
        'discovery_url' => 'https://contacts.example.org/dav/',
        'readonly' => true,
        'fixed' => ['username', 'password', 'discovery_url'],
    ];

The file is loaded after Mailu's defaults; ``unset($prefs['Mailu']);`` disables
the automatic Mailu preset. See the `RCMCardDAV administrator settings
<https://github.com/mstilkerich/rcmcarddav/blob/v5.1.3/doc/ADMIN-SETTINGS.md>`_
for other preset options. For per-user external credentials, users can add an
account in **Settings → CardDAV** instead. The ``%p`` preset placeholder refers
to Mailu's temporary webmail session token, so it cannot be used as a password
for an external DAV service.

Automatic Mailu CardDAV requests use the front container's HTTP or HTTPS port.
The front recognizes temporary webmail tokens only for connections originating
in ``SUBNET`` or ``SUBNET6``. Client discovery advertises the public ``/webdav/`` URL.

.. _header_authentication:

Header authentication using an external proxy
---------------------------------------------

The ``PROXY_AUTH_WHITELIST`` (default: unset/disabled) option allows you to configure a comma separated list of CIDRs of proxies to trust for authentication. This list is separate from ``REAL_IP_FROM`` and any entry in ``PROXY_AUTH_WHITELIST`` should also appear in ``REAL_IP_FROM``.

Use ``PROXY_AUTH_HEADER`` (default: 'X-Auth-Email') to customize which HTTP header the email address of the user to authenticate as should be and ``PROXY_AUTH_CREATE`` (default: False) to control whether non-existing accounts should be auto-created. Please note that Mailu doesn't currently support creating new users for non-existing domains; you do need to create all the domains that may be used manually.

Once configured, any request to /sso/login with the correct headers will be authenticated unless the "noproxyauth" parameter is passed, in which case the "standard" login form will be displayed. Please check issues `1972`_ and `2692`_ for more details.

Requests to:

- ``/sso/login`` use the browser preference from the last successful sign-in, defaulting to Webmail when enabled.
- ``/sso/login/admin`` explicitly select ``/admin``.
- ``/sso/login/webmail`` explicitly select ``/webmail``.
- Protected pages under ``/admin``, ``/roundcube`` and ``/snappymail`` return to the original
  page after authentication. Return destinations are stored server-side rather
  than placed in internally generated ``?url=`` links.

The ``mailu_signin_target`` cookie remembers only the selected application for one year. Explicit sign-in routes and protected-page return destinations override this preference. Existing same-origin ``?url=`` bookmarks remain supported.

Use ``PROXY_AUTH_LOGOUT_URL`` (default: unset) to redirect users to a specific URL after they have been logged out.

OAuth2 authentication for native mail clients
----------------------------------------------

Mailu provides an OAuth 2.0 issuer for native mail clients. The issuer uses
the primary ``HOSTNAME`` and the ``/admin`` path. OAuth is always
available and needs no extra environment variables. The draft -07 AutoConfig
document advertises the Mailu authorization and token endpoints, the public
``mailu`` client ID, and the ``imap smtp pop3 sieve offline_access`` scopes. Password
authentication and existing app tokens remain available.

OAuth access and refresh tokens use a dedicated signing key stored in Mailu's
database-backed config table. It is generated when OAuth tokens are first
issued and is independent of ``SECRET_KEY``, so rotating ``SECRET_KEY`` does not
invalidate OAuth tokens. Back up and share the database across admin replicas;
deleting or replacing this config entry invalidates OAuth tokens.

The authorization-code flow requires PKCE with ``S256``. Users sign in with
their Mailu account in the browser and approve mailbox access. Mailu issues
access tokens (24 hours by default) and rotating refresh tokens. Set
``OAUTH2_ACCESS_TOKEN_TTL`` in ``mailu.env`` to configure access-token lifetime
in seconds. Reuse of a rotated refresh
token revokes the entire grant family. For grants with ``offline_access``, an
access token never outlives the refresh token's absolute expiry or current idle
deadline. Set ``OAUTH2_REFRESH_TOKEN_TTL`` in
``mailu.env`` to control the absolute refresh token lifetime in seconds
(default: 7776000, or 90 days), and ``OAUTH2_REFRESH_TOKEN_IDLE`` to control
the maximum inactivity period (default: 604800, or one week). In the account settings,
users can review and revoke authorized mail apps separately from static app
tokens. The authorized-app list shows the client name, last token refresh, and
last mail connection address. Dovecot checks access tokens against Mailu's
private introspection endpoint and accepts ``OAUTHBEARER`` and ``XOAUTH2`` for
IMAP, SMTP, POP3, and ManageSieve. Thunderbird uses XOAUTH2. Each protocol
checks its corresponding scope,
and POP3 remains subject to the user's POP3 setting. Both the draft -07 and
legacy Thunderbird AutoConfig formats
prefer OAuth2 while retaining password authentication as a fallback. The
Thunderbird provider add-on on ``/admin/client`` recognizes every hostname in
``HOSTNAMES``.

OAuth authorization server metadata is available at
``/.well-known/oauth-authorization-server``. It advertises the authorization,
token, and revocation endpoints, supported scopes and grants, query response
mode, ``none`` client authentication at the token and revocation endpoints,
and PKCE with ``S256``.

Authorization responses include the ``iss`` parameter from RFC 9207 when the
issuer uses HTTPS, and metadata advertises this support. Password changes
expire existing OAuth access and refresh tokens and require each mail app to
authenticate again. The consent screen shows the public client ID; this ID
identifies the client registration but does not prove which application is
using it.

The consent screen lets users select the protocol scopes granted to each app.
The buttons appear in IMAP, POP3 (when enabled for the user), SMTP, SIEVE,
and ``offline_access`` order; hover over a button for its description.
``offline_access`` allows an app to refresh its access token without
another sign-in. If it is not granted, Mailu does not issue a refresh token and
the user must authorize the app again after the access token expires. The
Thunderbird add-on publishes a self-hosted update manifest; its manifest is
cached for one day and each versioned XPI is cached for one year.

.. _`1972`: https://github.com/Mailu/Mailu/issues/1972
.. _`2692`: https://github.com/Mailu/Mailu/issues/2692
