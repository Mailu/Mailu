Changelog
=========

Upgrade should run fine as long as you generate a new compose or stack
configuration and upgrade your mailu.env.

Please note that the current 1.8 is what we call a "soft release": It’s there for everyone to see and use, but to limit possible user-impact of this very big release, it’s not yet the default in the setup-utility for new users. When upgrading, please treat it with some care, and be sure to always have backups!

There are some changes to the configuration overrides. Override files are now mounted read-only into the containers.
The Dovecot and Postfix overrides are moved in their own sub-directory.
If there are local override files, they will need to be moved from overrides/ to overrides/dovecot and overrides/postfix/.
See https://mailu.io/1.8/faq.html#how-can-i-override-settings for all the mappings.

Please not that the shipped image for PostgreSQL database is deprecated.
We advise to switch to an external database server.

<!-- TOWNCRIER -->
v1.8.0 - 2020-09-28
--------------------

- Features: Add support for backward-forwarding using SRS ([#328](https://github.com/Mailu/Mailu/issues/328))
- Features: Add options to support different architectures builds ([#985](https://github.com/Mailu/Mailu/issues/985))
- Features: Add support for Traefik v2 certificate dumping ([#1011](https://github.com/Mailu/Mailu/issues/1011))
- Features: Resolve hosts to IPs if only HOST_* is set. If *_ADDRESS is set, leave it unresolved. ([#1113](https://github.com/Mailu/Mailu/issues/1113))
- Features: - Use nginx as http endpoint on kubernetes to simplify ingress ([#1158](https://github.com/Mailu/Mailu/issues/1158))
- Features: Advertise correct mail capabilities through the front-container, this also enables support for PIPELINING in mail-protocols and IMAP IDLE which is a (potential) performance gain. ([#1160](https://github.com/Mailu/Mailu/issues/1160))
- Features: Change default password scheme to PBKDF2 ([#1194](https://github.com/Mailu/Mailu/issues/1194))
- Features: Enable access log of admin service only for log levels of INFO and finer ([#1197](https://github.com/Mailu/Mailu/issues/1197))
- Features: japanese loca is now available ([#1207](https://github.com/Mailu/Mailu/issues/1207))
- Features: Allow to reject virus mails by setting ANTIVITUS_ACTION=reject ([#1259](https://github.com/Mailu/Mailu/issues/1259))
- Features: Update roundcube to 1.4.0 and enable the new elastic skin ([#1267](https://github.com/Mailu/Mailu/issues/1267))
- Features: The roundcube container does support mysql now (no setup integration yet) ([#1268](https://github.com/Mailu/Mailu/issues/1268))
- Features: Added CardDAV-Plugin for webmail roundcube. ([#1298](https://github.com/Mailu/Mailu/issues/1298))
- Features: Allow users to use server-sided full-text-search again by adding the dovecot fts-xapian plugin ([#1320](https://github.com/Mailu/Mailu/issues/1320))
- Features: Relay a domain to a nonstandard SMTP port by adding ":<port_num>" to the remote hostname or IP address. ([#1357](https://github.com/Mailu/Mailu/issues/1357))
- Features: Allow to enforce TLS for outbound mail by setting OUTBOUND_TLS_LEVEL=encrypt for postfix. ([#1478](https://github.com/Mailu/Mailu/issues/1478))
- Features: Introduce option to disable dovecot full-text-search by an enviroment variable. ([#1538](https://github.com/Mailu/Mailu/issues/1538))
- Features: Add support for AUTH LOGIN authentication mechanism for relaying email via smart hosts. ([#1635](https://github.com/Mailu/Mailu/issues/1635))
- Bugfixes: Fix the password encoding upon authentication ([#1139](https://github.com/Mailu/Mailu/issues/1139))
- Bugfixes: Fix piping mail into rspamd when moving from/to junk-folder ([#1177](https://github.com/Mailu/Mailu/issues/1177))
- Bugfixes: Separate HOST_ANTISPAM in HOST_ANTISPAM_MILTER and HOST_ANTISPAM_WEBUI because of different ports ([#1190](https://github.com/Mailu/Mailu/issues/1190))
- Bugfixes: Make postfix mailqueue persistent ([#1208](https://github.com/Mailu/Mailu/issues/1208))
- Bugfixes: Kubernetes manifests updated to be compatible with Kubernetes 1.16 (breaks compatibility with older k8s versions) ([#1241](https://github.com/Mailu/Mailu/issues/1241))
- Bugfixes: Use pip package for radicale to fix failing builds caused by [alpine]upstream package rebuild against different python version ([#1255](https://github.com/Mailu/Mailu/issues/1255))
- Bugfixes: Ratelimit counts up on failed auth only now ([#1278](https://github.com/Mailu/Mailu/issues/1278))
- Bugfixes: Disable Health checks on swarm mode ([#1289](https://github.com/Mailu/Mailu/issues/1289))
- Bugfixes: Enable the From header for message delivery report in Roundcube and ensure DKIM Signature ([#1381](https://github.com/Mailu/Mailu/issues/1381))
- Bugfixes: Fix alias resolution in regard to case: A specifically matching alias of wrong case is now preferred over a wildcard alias that might have »eaten« it previously. ([#1387](https://github.com/Mailu/Mailu/issues/1387))
- Bugfixes: Show SPF records in accordance with RFC 7208: Previously we instructed admins to create SPF and TXT records, where only TXT records are correct now. !! Attention !! You need to manually remove the SPF-typed records and keep only TXT in your DNS. ([#1394](https://github.com/Mailu/Mailu/issues/1394))
- Bugfixes: Cover relearning messages when moving bewteen Ham and Spam status ([#1438](https://github.com/Mailu/Mailu/issues/1438))
- Bugfixes: Defining POSTMASTER through setup tool apply also to DMARC_RUA and DMARC_RUF settings ([#1463](https://github.com/Mailu/Mailu/issues/1463))
- Bugfixes: Allow IPv6 authenticated connections in PostgreSQL pg_hba.conf ([#1479](https://github.com/Mailu/Mailu/issues/1479))
- Bugfixes: Check postfix mailqueue permissions before start-up ([#1486](https://github.com/Mailu/Mailu/issues/1486))
- Bugfixes: Fixes certbot renewal ([#1564](https://github.com/Mailu/Mailu/issues/1564))
- Improved Documentation: Added documentation that describes how spam filtering works in Mailu. ([#1167](https://github.com/Mailu/Mailu/issues/1167))
- Improved Documentation: Add documentation for the web administration interface. ([#1590](https://github.com/Mailu/Mailu/issues/1590))
- Deprecations and Removals: Dovecot: Delete obsolete data volume ([#1221](https://github.com/Mailu/Mailu/issues/1221))
- Misc:  ([#508](https://github.com/Mailu/Mailu/issues/508), [#1098](https://github.com/Mailu/Mailu/issues/1098), [#1214](https://github.com/Mailu/Mailu/issues/1214), [#1308](https://github.com/Mailu/Mailu/issues/1308), [#1444](https://github.com/Mailu/Mailu/issues/1444), [#1512](https://github.com/Mailu/Mailu/issues/1512))


v1.7.0 - 2019-08-22
-------------------

Upgrade should run fine as long as you generate a new compose or stack
configuration and upgrade your mailu.env.

If you run the PostgreSQL server, the database was upgrade, so you will need to
dump the database before upgrading and load the dump after the upgrade is
complete. Please not that the shipped image for PostgreSQL database will be
deprecated before 1.8.0, you can switch to an external database server by then.

- Deprecation: using the internal postgres image will be deprecated by 1.8.0
- Features: Update Fetchmail to 7.0.0, which features more current SSL support ([#891](https://github.com/Mailu/Mailu/issues/891))
- Features: Relays with authentication ([#958](https://github.com/Mailu/Mailu/issues/958))
- Features: Fixed hardcoded antispam and antivirus host addresses ([#979](https://github.com/Mailu/Mailu/issues/979))
- Features: Add sidebar toggle ([#988](https://github.com/Mailu/Mailu/issues/988))
- Features: Don’t use complicated rsyslogd logging in postfix anymore, instead start the daemon directly — configured to log to stdout. ([#1049](https://github.com/Mailu/Mailu/issues/1049))
- Features: Update alpine to 3.10 and clean up the ensuing problems. ([#1051](https://github.com/Mailu/Mailu/issues/1051))
- Features: Update user password in commandline ([#1066](https://github.com/Mailu/Mailu/issues/1066))
- Features: use HTTP/1.1 for proxyied connections ([#1070](https://github.com/Mailu/Mailu/issues/1070))
- Features: Update Rainloop to 1.13.0 ([#1071](https://github.com/Mailu/Mailu/issues/1071))
- Features: Use python package socrate instead of Mailustart ([#1082](https://github.com/Mailu/Mailu/issues/1082))
- Bugfixes: Use ldez/traefik-certs-dumper in our certificate dumper to have a more robust solution ([#820](https://github.com/Mailu/Mailu/issues/820))
- Bugfixes: Make aliases optionally case-insensitive: After attempting to resolve an alias in its preserved case, also attempt to match it case-insensitively ([#867](https://github.com/Mailu/Mailu/issues/867))
- Bugfixes: Fix HOST_* variable usage ([#884](https://github.com/Mailu/Mailu/issues/884))
- Bugfixes: Fix DKIM-DNS entries in admin webinterface ([#1075](https://github.com/Mailu/Mailu/issues/1075))
- Bugfixes: Allow subnet with host bit set in setup ([#1083](https://github.com/Mailu/Mailu/issues/1083))
- Bugfixes: Support domain literals ([#1087](https://github.com/Mailu/Mailu/issues/1087))
- Bugfixes: Fix creating new fetched accounts
- Bugfixes: Fix poor performance if ANTIVIRUS is configured to none.
- Bugfixes: Implement mailustart to resolve webmail in admin ([#716](https://github.com/Mailu/Mailu/issues/716))
- Bugfixes: Rename cli commands and their options (replace "\_" with "-") ([#877](https://github.com/Mailu/Mailu/issues/877))
- Bugfixes: Fix typo in migration script ([#905](https://github.com/Mailu/Mailu/issues/905))
- Bugfixes: Fix redis hostname in admin
- Improved Documentation: Move the localization effort to Weblate ([#916](https://github.com/Mailu/Mailu/issues/916))
- Enhancement: Distinguish disabled user in user list view by row color
- Enhancement: Make Unbound drop privileges after binding to port
- Enhancement: Stop using static assets, but build them using Webpack
- Enhancement: Create an Authentication Token with IPv6 address restriction ([#829](https://github.com/Mailu/Mailu/issues/829))
- Enhancement: Automatically create admin user on container startup if given appropriate environment variables
- Enhancement: Missing wildcard option in alias flask command ([#869](https://github.com/Mailu/Mailu/issues/869))

v1.6.0 - 2019-01-18
-------------------

- Global: Architecture of the central container ([#56](https://github.com/Mailu/Mailu/issues/56), [#108](https://github.com/Mailu/Mailu/issues/108))
- Global: Serve documentation with docker ([#601](https://github.com/Mailu/Mailu/issues/601), [#608](https://github.com/Mailu/Mailu/issues/608))
- Global: Travis-CI automated test build ([#602](https://github.com/Mailu/Mailu/issues/602))
- Global: Abstract db access from Postfix and Dovecot ([#612](https://github.com/Mailu/Mailu/issues/612))
- Global: Refactor the admin architecture and configuration management ([#670](https://github.com/Mailu/Mailu/issues/670))
- Feature: Used quota in admin interface ([#216](https://github.com/Mailu/Mailu/issues/216))
- Feature: User Signup ([#281](https://github.com/Mailu/Mailu/issues/281), [#340](https://github.com/Mailu/Mailu/issues/340))
- Feature: Client setup page ([#342](https://github.com/Mailu/Mailu/issues/342))
- Feature: Administration setup page ([#343](https://github.com/Mailu/Mailu/issues/343))
- Feature: Visual notice whether the mx record points to mailu server ([#356](https://github.com/Mailu/Mailu/issues/356))
- Feature: Option for vacation start ([#362](https://github.com/Mailu/Mailu/issues/362))
- Feature: Enable enigma in Roundcube ([#391](https://github.com/Mailu/Mailu/issues/391))
- Feature: Allow more charcaters as a valid email address ([#443](https://github.com/Mailu/Mailu/issues/443))
- Feature: IDNA support ([#446](https://github.com/Mailu/Mailu/issues/446))
- Feature: Disable user account  ([#449](https://github.com/Mailu/Mailu/issues/449))
- Feature: Use fuzzy hashes in rpamd ([#456](https://github.com/Mailu/Mailu/issues/456), [#527](https://github.com/Mailu/Mailu/issues/527))
- Feature: Enable “doveadm -A” command ([#458](https://github.com/Mailu/Mailu/issues/458))
- Feature: Remove the Service Status page ([#463](https://github.com/Mailu/Mailu/issues/463))
- Feature: Automated Releases ([#487](https://github.com/Mailu/Mailu/issues/487))
- Feature: Support for ARC ([#495](https://github.com/Mailu/Mailu/issues/495))
- Feature: Add posibilty to run webmail on root ([#501](https://github.com/Mailu/Mailu/issues/501))
- Feature: Documentation to deploy mailu on a docker swarm ([#551](https://github.com/Mailu/Mailu/issues/551))
- Feature: Add optional Maildir-Compression ([#553](https://github.com/Mailu/Mailu/issues/553))
- Feature: Preserve rspamd history on container restart ([#561](https://github.com/Mailu/Mailu/issues/561))
- Feature: FAQ ([#564](https://github.com/Mailu/Mailu/issues/564), [#677](https://github.com/Mailu/Mailu/issues/677))
- Feature: Kubernetes support ([#576](https://github.com/Mailu/Mailu/issues/576))
- Feature: Option to bounce or reject email when recipient is unknown ([#583](https://github.com/Mailu/Mailu/issues/583), [#626](https://github.com/Mailu/Mailu/issues/626))
- Feature: implement healthchecks for all containers ([#631](https://github.com/Mailu/Mailu/issues/631))
- Feature: Option to send front logs to journald or syslog ([#584](https://github.com/Mailu/Mailu/issues/584), [#661](https://github.com/Mailu/Mailu/issues/661))
- Feature: Support bcrypt and PBKDF2 ([#647](https://github.com/Mailu/Mailu/issues/647), [#667](https://github.com/Mailu/Mailu/issues/667))
- Feature: enable http2 ([#674](https://github.com/Mailu/Mailu/issues/674))
- Feature: Unbound DNS as optional service ([#681](https://github.com/Mailu/Mailu/issues/681))
- Feature: Re-write test suite ([#682](https://github.com/Mailu/Mailu/issues/682))
- Feature: Docker image prefixes ([#702](https://github.com/Mailu/Mailu/issues/702))
- Feature: Add authentication method “login” for Outlook ([#704](https://github.com/Mailu/Mailu/issues/704))
- Feature: Allow extending nginx config with overrides ([#713](https://github.com/Mailu/Mailu/issues/713))
- Feature: Dynamic attachment size limit ([#731](https://github.com/Mailu/Mailu/issues/731))
- Feature: Certificate watcher for external certs to reload nginx ([#732](https://github.com/Mailu/Mailu/issues/732))
- Feature: Kubernetes
- Feature: Supports postgresql and mysql database backends ([#420](https://github.com/Mailu/Mailu/issues/420))
- Enhancement: Use pre-defined dhparam ([#322](https://github.com/Mailu/Mailu/issues/322))
- Enhancement: Disable ssl_session_tickets ([#329](https://github.com/Mailu/Mailu/issues/329))
- Enhancement: max attachment size in roundcube ([#338](https://github.com/Mailu/Mailu/issues/338))
- Enhancement: Use x-forwarded-proto with redirects ([#347](https://github.com/Mailu/Mailu/issues/347))
- Enhancement: Added adress verification before accepting mails for delivery ([#353](https://github.com/Mailu/Mailu/issues/353))
- Enhancement: Reverse proxy - Real ip header and mail-letsencrypt ([#358](https://github.com/Mailu/Mailu/issues/358))
- Enhancement: Parametrize hosts ([#373](https://github.com/Mailu/Mailu/issues/373))
- Enhancement: Expose ports in dockerfiles ([#392](https://github.com/Mailu/Mailu/issues/392))
- Enhancement: Added webmail-imap dependency in docker-compose ([#403](https://github.com/Mailu/Mailu/issues/403))
- Enhancement: Add environment variables to allow running outside of docker-compose ([#429](https://github.com/Mailu/Mailu/issues/429))
- Enhancement: Add original Delivered-To header to received messages ([#433](https://github.com/Mailu/Mailu/issues/433))
- Enhancement: Use HOST_ADMIN in "Forwarding authentication server" ([#436](https://github.com/Mailu/Mailu/issues/436), [#437](https://github.com/Mailu/Mailu/issues/437))
- Enhancement: Use POD_ADDRESS_RANGE for Dovecot ([#448](https://github.com/Mailu/Mailu/issues/448))
- Enhancement: Using configurable filenames for TLS certs ([#468](https://github.com/Mailu/Mailu/issues/468))
- Enhancement: Don't require BootstrapCDN (GDPR-compliance) ([#477](https://github.com/Mailu/Mailu/issues/477))
- Enhancement: Use dynamic client_max_body_size for webmail ([#502](https://github.com/Mailu/Mailu/issues/502))
- Enhancement: New logo design ([#509](https://github.com/Mailu/Mailu/issues/509))
- Enhancement: New manifests for Kubernetes ([#544](https://github.com/Mailu/Mailu/issues/544))
- Enhancement: Pin Alpine image ([#548](https://github.com/Mailu/Mailu/issues/548), [#557](https://github.com/Mailu/Mailu/issues/557))
- Enhancement: Use safer cipher in roundcube ([#597](https://github.com/Mailu/Mailu/issues/597))
- Enhancement: Improve sender checks ([#633](https://github.com/Mailu/Mailu/issues/633))
- Enhancement: Use PHP 7.2 for rainloop and roundcube ([#606](https://github.com/Mailu/Mailu/issues/606), [#642](https://github.com/Mailu/Mailu/issues/642))
- Enhancement: Multi-version documentation ([#664](https://github.com/Mailu/Mailu/issues/664))
- Enhancement: Contribution documentation ([#700](https://github.com/Mailu/Mailu/issues/700))
- Enhancement: Move Mailu Docker network to a fixed subnet ([#727](https://github.com/Mailu/Mailu/issues/727))
- Enhancement: Added regex validation for alias username ([#764](https://github.com/Mailu/Mailu/issues/764))
- Enhancement: Allow to disable aliases or users for a specific domain ([#799](https://github.com/Mailu/Mailu/issues/799))
- Enhancement: Update documentation
- Enhancement: Include favicon package ([#801](https://github.com/Mailu/Mailu/issues/801), ([#802](https://github.com/Mailu/Mailu/issues/802))
- Enhancement: Add logging at critical places in python start.py scripts. Implement LOG_LEVEL to control verbosity ([#588](https://github.com/Mailu/Mailu/issues/588))
- Enhancement: Mark message as seen when reporting as spam
- Enhancement: Better support and document IPv6 ([#827](https://github.com/Mailu/Mailu/issues/827))
- Upstream: Update Roundcube
- Upstream: Update Rainloop
- Bug: Rainloop fails with "domain not allowed" ([#93](https://github.com/Mailu/Mailu/issues/93))
- Bug: Announces fail ([#309](https://github.com/Mailu/Mailu/issues/309))
- Bug: Authentication issues with rspamd admin ui ([#315](https://github.com/Mailu/Mailu/issues/315))
- Bug: front hangup on restart ([#341](https://github.com/Mailu/Mailu/issues/341))
- Bug: Display the proper user quota when set to 0/infinity ([#345](https://github.com/Mailu/Mailu/issues/345))
- Bug: Domain details button "Regenerate keys" when no keys are generated yet ([#346](https://github.com/Mailu/Mailu/issues/346))
- Bug: Relayed Domains: access denied error ([#351](https://github.com/Mailu/Mailu/issues/351))
- Bug: Do not deny HTTP access upon TLS error when the flavor is mail ([#352](https://github.com/Mailu/Mailu/issues/352))
- Bug: php_zip extension missing in Roundcube webmail ([#364](https://github.com/Mailu/Mailu/issues/364))
- Bug: RoundCube webmail .htaccess assumes PHP 5 ([#366](https://github.com/Mailu/Mailu/issues/366))
- Bug: No quota shows "0 Bytes" in user list ([#368](https://github.com/Mailu/Mailu/issues/368))
- Bug: RELAYNETS not honored when login is different from sender ([#369](https://github.com/Mailu/Mailu/issues/369))
- Bug: Request Entity Too Large ([#371](https://github.com/Mailu/Mailu/issues/371))
- Bug: Pass the full host to the backend ([#372](https://github.com/Mailu/Mailu/issues/372))
- Bug: Can't send from an email account that has forwarding ([#390](https://github.com/Mailu/Mailu/issues/390))
- Bug: SSL protocol error roundcube/imap ([#411](https://github.com/Mailu/Mailu/issues/411), [#414](https://github.com/Mailu/Mailu/issues/414))
- Bug: Unable to send from alternative domains ([#415](https://github.com/Mailu/Mailu/issues/415))
- Bug: Webadmin redirect ignores host port ([#419](https://github.com/Mailu/Mailu/issues/419))
- Bug: Disable esld when signing with dkim ([#435](https://github.com/Mailu/Mailu/issues/435))
- Bug: DKIM missing when using identities ([#462](https://github.com/Mailu/Mailu/issues/462))
- Bug: Moving mails from Junk to Trash flags them as ham ([#474](https://github.com/Mailu/Mailu/issues/474))
- Bug: Cannot set the "keep emails" for fetched accounts ([#479](https://github.com/Mailu/Mailu/issues/479))
- Bug: CVE-2018-8740 ([#482](https://github.com/Mailu/Mailu/issues/482))
- Bug: Hide administration header in sidebar for normal users ([#505](https://github.com/Mailu/Mailu/issues/505))
- Bug: Return correct status codes from auth rate limiter failure ([#513](https://github.com/Mailu/Mailu/issues/513))
- Bug: Domain edit page shows "Create" button ([#523](https://github.com/Mailu/Mailu/issues/523))
- Bug: Hostname resolving in start.py should retry on failure [docker swarm]  ([#555](https://github.com/Mailu/Mailu/issues/555))
- Bug: Error when trying to log in with an account without domain ([#585](https://github.com/Mailu/Mailu/issues/585))
- Bug: Fix rainloop permissions ([#637](https://github.com/Mailu/Mailu/issues/637))
- Bug: Fix broken webmail and logo url in admin ([#792](https://github.com/Mailu/Mailu/issues/792))
- Bug: Don't allow negative values on domain creation/edit ([#799](https://github.com/Mailu/Mailu/issues/799))
- Bug: Don't recursivly chown on mailboxes ([#776](https://github.com/Mailu/Mailu/issues/776))
- Bug: Fix forced password input for user edit ([#745](https://github.com/Mailu/Mailu/issues/745))
- Bug: Fetched accounts: Password field is of type "text" ([#789](https://github.com/Mailu/Mailu/issues/789))
- Bug: Auto-forward destination not accepting top level domains ([#818](https://github.com/Mailu/Mailu/issues/818))
- Bug: DOMAIN_REGISTRATION=False in .env was not treated correctly ([#830](https://github.com/Mailu/Mailu/issues/830))
- Bug: Internal error when checking null sender address ([#846](https://github.com/Mailu/Mailu/issues/846))

v1.5.1 - 2017-11-21
-------------------

- Global: add a DNS-based instance count tracker, use the ``DISABLE_STATISTICS``
  setting to disable it.
- Global: specify container dependencies in the Compose configuration, update
  your ``docker-compose.yml``.
- Feature: add a *mail* TLS flavor that only enforces TLS for email connections.
- Feature: welcome emails, see the configuration for details
- Feature: end date for vacations, see the automatic reply page
- L10N: dutch loca is now available
- L10N: swedish loca is now available
- L10N: italian loca is now partially available
- L10N: chinese loca is now available
- Upstream: upgrade to Roundcube 1.3.3
- Enhancement: use the alpine image for redis
- Enhancement: use a dynamic worker count for Nginx
- Bug: fix the pop3 proxy
- Bug: fix DNS resolution bugs in the frontend
- Bug: fix Webdav authentication
- Bug: properly honor enabled features (imap and pop3) per user

v1.5.0 - 2017-11-05
-------------------

- Global: clean the ``.env`` file and change many options, *make sure
  that you download the latest ``.env`` and apply your settings when migrating.*
- Global: clean the Compose configuration, *make sure that you download the
  latest ``docker-compose.yml`` when migrating.*
- Global: nginx is now a reverse proxy for HTTP, SMTP, IMAP and POP.
- Global: the new Rainloop webmail is available.
- Global: the mail stack now supports IPv6.
- Global: most images moved to Alpine.
- Global: the documentation moved to a Sphinx directory.
- Global: deprecate rmilter and use rspamd proxy instead.
- Feature: multiple TLS flavors are available, see the ``TLS_FLAVOR`` setting.
- Feature: alternative domains now act as a copy of a given domain.
- Feature: relay domains now act as a mail relay (e.g. for backup servers).
- Feature: the server now supports multiple public names, with letsencrypt.
- Feature: authentication tokens can be generated per client.
- Feature: the manage.py CLI has many options to import and manage a setup.
- Feature: add overrides for the Postfix configuration.
- Feature: allow to keep or discard forwarded messages.
- Feature: make password encryption scheme configurable.
- Feature: make DMARC rua configurable.
- Feature: Clamav may now be disabled completely.
- Feature: support a configurable recipient delimiter for address extension.
- Feature: the admin interface points to the webmail and a configurable site.
- L10N: portugese loca is now available
- Upstream: upgrade to Roundcube 1.3.2
- Upstream: upgrade to Rainloop 1.11.3
- Upstream: upgrade to Dovecot 2.2.33
- Upstream: upgrade to Postfix 3.2.4
- Bug: the Postfix queue is now persisted.
- Bug: certbot now handle renewal properly.
- Bug: fix sender and recipient restrictions for antispam features.
- Bug: webmails now handle large attachments.
- Bug: dhparam are now generated properly on the frontend.

v1.4.0 - 2017-02-12
-------------------

- Global: make sure that ``DEBUG`` is commented in your ``.env`` if you
  disabled it and update your ``docker-compose.yml``
- Global: now only using proper upstream packages
- Security: disable verbose logging of passwords by the fetchmail script
- Security: the SMTP TLS configuration was improved
- Feature: certbot certificate generation is available, uncomment
  ``ENABLE_CERTBOT`` in your ``.env`` to enable it
- Feature: fetched emails can now be kept on the remote server
- Feature: a maximum quota can now be configured per domain
- Feature: admins can now send public announcements
- Feature: managesieve is enabled and configured in Webmails automatically
- Feature: a DAV server is available
- L10N: language is selected automatically based on HTTP headers
- L10N: french loca is now available
- L10N: german loca is now available
- L10N: dutch loca is now available
- Upstream: upgrade to Roundcube 1.2.3
- Upstream: upgrade to Dovecot 2.2.27
- Bug: mail forwards are now handled by Postfix directly to avoid many bugs
  with sieve forwards
- Bug: fixed multiple bugs in the admin UI

v1.3.0 - 2016-11-05
-------------------

- Global: renamed the project to Mailu
- Global: renamed ``freeposte.env`` as ``.env`` and distribute dist files

  Have a look at https://github.com/Mailu/Mailu/wiki/Migrate-from-Freeposte-to-Mailu
  for migrating to the new project

- Security: disabled access to extdata from user-written sieve scripts
- Security: increased Postfix delivery restrictions, will help against spam as
  well
- Feature: setup I18N for the admin interface
- Enhancement: improved database models
- Upstream: upgrade to Roundcube 1.2.2
- Upstream: upgrade to Dovecot 2.2.6

v1.2.1 - 2016-09-28
-------------------

- Bug: fix the migration script regarding wildcard aliases.

  If you installed 1.2.0 and migrated already, simply run this against your
  sqlite database:

      UPDATE alias SET wildcard=0 WHERE wildcard IS NULL;

v1.2.0 - 2016-08-19
-------------------

- Security: apply TLS best practices from BetterCrypto
- Security: remove most remote assets
- Security: add CSRF checks to all administrative actions
- Feature: offer configuration overrides for Postfix and Dovecot
- Feature: offer to send emails through a relay host

  After migrating, make sure that you update your ``freeposte.env`` accordingly

- Feature: support wildcard and catch-all aliases
- Feature: honor the per-user spam settings
- Enhancement: start maintaining a Changelog
- Upstream: upgrade to Roundcube 1.2.1
- Upstream: upgrade to Dovecot 2.2.5
