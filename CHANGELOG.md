Changelog
=========

For full details see the [releases page](https://mailu.io/2.0/releases.html)

Upgrade should run fine as long as you generate a new docker-compose.yml file and mailu.env file via setup.mailu.io.
After that any old settings can be reapplied to mailu.env.
Before making any changes, carefully read the [configuration reference](https://mailu.io/2.0/configuration.html). New settings have been introduced and some settings have been removed.
Multiple changes have been made to the docker-compose.yml file and mailu.env file.

If you use Fail2Ban, then the Fail2Ban intructions have been improved. It is mandatory to remove your Fail2Ban config and re-apply it using the instructions from the [documentation](https://mailu.io/2.0/faq.html#do-you-support-fail2ban).

Please note that once you have upgraded to 2.0 you won't be able to roll-back to earlier versions

After changing mailu.env, it is required to recreate all containers for the changes to be propagated.

2.0.0 - 2023-04-03

- Features: Provide auto-configuration files (autodiscover, autoconfig & mobileconfig); Please update your DNS records ([#224](https://github.com/Mailu/Mailu/issues/224))
- Features: Introduction of the Mailu RESTful API. The full Mailu config can be changed via the Mailu API.
  See the section Mailu RESTful API & the section configuration reference in the documentation for more information. ([#445](https://github.com/Mailu/Mailu/issues/445))
- Features: Allow other folders to be synced by fetchmail ([#711](https://github.com/Mailu/Mailu/issues/711))
- Features: Update the webmail images.
  Roundcube
    - Switch to base image (alpine)
    - Switch to php-fpm
  SnappyMail
    - Switch to base image
    - Upgrade php7 to php8. ([#1521](https://github.com/Mailu/Mailu/issues/1521))
- Features: Implement Header authentication via external proxy ([#1972](https://github.com/Mailu/Mailu/issues/1972))
- Features: Add FETCHMAIL_ENABLED to toggle the fetchmail functionality in the admin interface ([#2127](https://github.com/Mailu/Mailu/issues/2127))
- Features: Create a polite and turtle delivery queue to accommodate destinations that expect emails to be sent slowly ([#2213](https://github.com/Mailu/Mailu/issues/2213))
- Features: Add support for custom NGINX config in /etc/nginx/conf.d. ([#2221](https://github.com/Mailu/Mailu/issues/2221))
- Features: Added ability to mark spam mails as read or unread when moving to junk folder. ([#2278](https://github.com/Mailu/Mailu/issues/2278))
- Features: Switch from RainLoop to SnappyMail. SnappyMail has better performance and is more secure. ([#2295](https://github.com/Mailu/Mailu/issues/2295))
- Features: Configurable default spam threshold used for new users ([#2328](https://github.com/Mailu/Mailu/issues/2328))
- Features: Create a GUI for WILDCARD_SENDERS ([#2372](https://github.com/Mailu/Mailu/issues/2372))
- Features: Prevent signups with accounts for which an SQL-LIKE alias exists. ([#2429](https://github.com/Mailu/Mailu/issues/2429))
- Features: Introduce TLS_PERMISSIVE, a new advanced setting to harden cipher configuration on port 25. Changing the default is strongly discouraged, please read the documentation before doing so. ([#2449](https://github.com/Mailu/Mailu/issues/2449))
- Features: Upgrade the anti-spoofing rule. We shouldn't assume that Mailu is the only MTA allowed to send emails on behalf of the domains it hosts... but we should also ensure that both the envelope from and header from are checked. ([#2475](https://github.com/Mailu/Mailu/issues/2475))
- Features: Implement the required glue to make "doveadm -A" work ([#2498](https://github.com/Mailu/Mailu/issues/2498))
- Features: Implement a minimum length for passwords of 8 characters. Check passwords upon login against HaveIBeenPwned and warn users if their passwords are compromised. ([#2500](https://github.com/Mailu/Mailu/issues/2500))
- Features: Implement OLETools and block bad macros in office documents ([#2510](https://github.com/Mailu/Mailu/issues/2510))
- Features: Switch to GrapheneOS's hardened_malloc ([#2525](https://github.com/Mailu/Mailu/issues/2525))
- Features: New override system for Rspamd. In the old system, all files were placed in the Rspamd overrides folder.
  These overrides would override everything, including the Mailu Rspamd config.

  Now overrides are placed in /overrides.
  If you use your own map files, change the location to /override/myMapFile.map in the corresponding conf file.
  It works as following.
  * If the override file overrides a Mailu defined config file,
    it will be included in the Mailu config file with lowest priority.
    It will merge with existing sections.
  * If the override file does not override a Mailu defined config file,
    then the file will be placed in the rspamd local.d folder.
    It will merge with existing sections.

  For more information, see the description of the local.d folder on the rspamd website:
  https://www.rspamd.com/doc/faq.html#what-are-the-locald-and-overrided-directories ([#2555](https://github.com/Mailu/Mailu/issues/2555))
- Features: Adds a button to the roundcube interface that gets you back to the admin interface ([#2591](https://github.com/Mailu/Mailu/issues/2591))
- Features: Drop postfix rsyslog localhost messages with IPv6 address ([#2594](https://github.com/Mailu/Mailu/issues/2594))
- Features: Isolate radicale and webmail on their own network. This ensures they don't have privileged access to any of the other containers. ([#2613](https://github.com/Mailu/Mailu/issues/2613))
- Features: Improved IPv6 support ([#2630](https://github.com/Mailu/Mailu/issues/2630))
- Features: Provide a changelog for minor releases. The github release will now:
  * Provide the changelog message from the newsfragment of the PR that triggered the backport.
  * Provide a github link to the PR/issue of the PR that was backported.

  Switch to building multi-arch images. The images build for pull requests, master and production
  are now multi-arch images for the architectures:
  * linux/amd64
  * linux/arm64/v8
  * linux/arm/v7

  Enhance CI/CD workflow with retry functionality. All steps for building images are now automatically
  retried. If a build temporarily fails due to a network error, the retried step will still succeed. ([#2653](https://github.com/Mailu/Mailu/issues/2653))
- Features: Add Czech translation for web administration interface. ([#2676](https://github.com/Mailu/Mailu/issues/2676))
- Features: Allow inbound to http and mail ports to accept the PROXY protocol ([#2717](https://github.com/Mailu/Mailu/issues/2717))
- Bugfixes: Add an option so that emails fetched with fetchmail don't go through the filters (closes #1231) ([#1231](https://github.com/Mailu/Mailu/issues/1231))
- Bugfixes: Allow '+' in the localpart of email addresses to forward to ([#1236](https://github.com/Mailu/Mailu/issues/1236))
- Bugfixes: Do not update the updated_at field of the User model when quota_bytes_used is updated ([#1363](https://github.com/Mailu/Mailu/issues/1363))
- Bugfixes: Remove postfix's master.pid on startup if there is no other instance running ([#1483](https://github.com/Mailu/Mailu/issues/1483))
- Bugfixes: updated Dockerfile to alpine 3.14.3 to address several CVEs ([#2099](https://github.com/Mailu/Mailu/issues/2099))
- Bugfixes: The gpg-agent package was missing due to updating to a new debian version.
  This fix adds gpg-agent back to the roundcube image.
  It is used for the enigmail roundcube plugin. ([#2117](https://github.com/Mailu/Mailu/issues/2117))
- Bugfixes: Fix CI/CD workflow. Tags were not set to the correct commit hash. ([#2124](https://github.com/Mailu/Mailu/issues/2124))
- Bugfixes: Fix a bug preventing mailu from being usable when no webmail is configured ([#2125](https://github.com/Mailu/Mailu/issues/2125))
- Bugfixes: Enable unbound by default. Mailu now requires a DNSSEC validating DNS resolver and experience has shown that this may not be the default everywhere yet. ([#2135](https://github.com/Mailu/Mailu/issues/2135))
- Bugfixes: Pin the root certificate differently for DANE. If you have setup a TLSA record following previous suggestion from Mailu please update it. ([#2138](https://github.com/Mailu/Mailu/issues/2138))
- Bugfixes: Remove the misleading text in mailu.env that zstd and lz4 are supported for dovecot mail compression.
  Zstd and lz4 are not supported. The reason is that the alpine project does not compile this
  into the dovecot package.
  Users who want this funcionality, can kindly request the alpine project to compile dovecot
  with lz4&zstd support. ([#2139](https://github.com/Mailu/Mailu/issues/2139))
- Bugfixes: Update roundcube to 1.5.2 to fixe an XSS ([#2141](https://github.com/Mailu/Mailu/issues/2141))
- Bugfixes: matching rainloop php to roundcube's: timezone is a parameter in mailu.env ([#2193](https://github.com/Mailu/Mailu/issues/2193))
- Bugfixes: Added the /overrides directory in the roundcube config.inc.php file ([#2195](https://github.com/Mailu/Mailu/issues/2195))
- Bugfixes: Configuring pwstore_scheme in carddav plugin with des_key because Mailu is incompatible with encrypted
  https://github.com/mstilkerich/rcmcarddav/blob/master/doc/ADMIN-SETTINGS.md#password-storing-scheme ([#2196](https://github.com/Mailu/Mailu/issues/2196))
- Bugfixes: Switch from DST_ROOT_X3 to ISRG_X1 as alpine is not shipping the former anymore ([#2199](https://github.com/Mailu/Mailu/issues/2199))
- Bugfixes: Will update /etc/nginx/nginx.conf and /etc/nginx/http.d/rainloop.conf in webmail container to support MESSAGE_SIZE_LIMIT ([#2207](https://github.com/Mailu/Mailu/issues/2207))
- Bugfixes: Add input validation for domain creation ([#2210](https://github.com/Mailu/Mailu/issues/2210))
- Bugfixes: Make public announcement bypass the filters. They may still time-out before being sent if there is a large number of users. ([#2231](https://github.com/Mailu/Mailu/issues/2231))
- Bugfixes: Work around a bug in coredns: set the DO flag on our DNSSEC queries. Add a new FAQ entry to explain our DNSSEC requirements and ensure that our error message points to it. ([#2239](https://github.com/Mailu/Mailu/issues/2239))
- Bugfixes: Fetchmail: Missing support for '*_ADDRESS' env vars ([#2246](https://github.com/Mailu/Mailu/issues/2246))
- Bugfixes: Fix broken setup. Not all dependencies were pinned resulting in a broken update being pulled. ([#2249](https://github.com/Mailu/Mailu/issues/2249))
- Bugfixes: Fix a bug where rspamd may trigger HFILTER_HOSTNAME_UNKNOWN if part of the delivery chain was using ipv6 ([#2260](https://github.com/Mailu/Mailu/issues/2260))
- Bugfixes: Update to Alpine Linux 3.14.4 which contains a security fix for openssl. ([#2281](https://github.com/Mailu/Mailu/issues/2281))
- Bugfixes: Fixed AUTH_RATELIMIT_IP not working on imap/pop3/smtp. ([#2284](https://github.com/Mailu/Mailu/issues/2284))
- Bugfixes: update alpine linux docker image to version 3.14.5 which includes a security fix for zlib’s CVE-2018-25032. ([#2302](https://github.com/Mailu/Mailu/issues/2302))
- Bugfixes: postfix: wrap IPv6 CIDRs in square brackets for RELAYNETS ([#2325](https://github.com/Mailu/Mailu/issues/2325))
- Bugfixes: Disable the built-in nginx resolver for traffic going through the mail plugin. This will silence errors about DNS resolution when the connecting host has no rDNS. ([#2346](https://github.com/Mailu/Mailu/issues/2346))
- Bugfixes: Re-enable the built-in nginx resolver for traffic going through the mail plugin.
  This is required for passing rDNS/ptr information to postfix.
  Without this rspamd will flag all messages with DHFILTER_HOSTNAME_UNKNOWN due to the missing rDNS/ptr info. ([#2368](https://github.com/Mailu/Mailu/issues/2368))
- Bugfixes: Roundcube overrides now also include .inc.php files. Only .inc.php should be used moving forward. ([#2388](https://github.com/Mailu/Mailu/issues/2388))
- Bugfixes: Forwarding emails user setting did not support 1 letter domains. ([#2402](https://github.com/Mailu/Mailu/issues/2402))
- Bugfixes: Update roundcube to 1.5.3
  Update rcmcarddav plugin to 4.4.2 ([#2415](https://github.com/Mailu/Mailu/issues/2415))
- Bugfixes: Switch from mysqlclient to mysql-connector explicitely ([#2432](https://github.com/Mailu/Mailu/issues/2432))
- Bugfixes: Enable rspamd's autolearn feature to ensure that its bayes classifier has enough HAM to make it usable. Previously the bayes module would never work unless some HAM had been learnt manually. ([#2447](https://github.com/Mailu/Mailu/issues/2447))
- Bugfixes: Fix a bug preventing users without IMAP access to access the webmails ([#2451](https://github.com/Mailu/Mailu/issues/2451))
- Bugfixes: Ensure that Mailu keeps working even if it can't obtain a certificate from letsencrypt for one of the HOSTNAMES ([#2467](https://github.com/Mailu/Mailu/issues/2467))
- Bugfixes: Quote SMTP SIZE to avoid splitting keyword and parameter in EHLO response ([#2485](https://github.com/Mailu/Mailu/issues/2485))
- Bugfixes: Upgrade to alpine 3.16.2 ([#2497](https://github.com/Mailu/Mailu/issues/2497))
- Bugfixes: Fix: include start and end dates in the auto-reply period ([#2512](https://github.com/Mailu/Mailu/issues/2512))
- Bugfixes: Fix creation of deep structures using import in update mode ([#2601](https://github.com/Mailu/Mailu/issues/2601))
- Bugfixes: Speak HAPROXY protocol in between front and smtp and front and imap. This ensures the backend is aware of the real client IP and whether TLS was used. ([#2603](https://github.com/Mailu/Mailu/issues/2603))
- Bugfixes: Fix a bug introduced in master whereby anything locally generated (sieve, autoresponder, ...) would be blocked by the anti-spoofing rules ([#2633](https://github.com/Mailu/Mailu/issues/2633))
- Bugfixes: Fix sieve/out of office replies by adding SUBNET to rspamd's local_networks ([#2635](https://github.com/Mailu/Mailu/issues/2635))
- Bugfixes: Uses the correct From address (instead of an SRS alias) in the sieve/vacation module ([#2640](https://github.com/Mailu/Mailu/issues/2640))
- Bugfixes: Tell roundcube to use UTF8 instead of 'UTF7-IMAP' when creating sieve scripts. ([#2650](https://github.com/Mailu/Mailu/issues/2650))
- Bugfixes: Tweak the snuffleupagus rules to make roundcube's caldav work ([#2693](https://github.com/Mailu/Mailu/issues/2693))
- Bugfixes: Proxy authentication was using the real client ip instead of the proxy
  IP for checking the PROXY_AUTH_WHITELIST. ([#2708](https://github.com/Mailu/Mailu/issues/2708))
- Improved Documentation: remove the / in the location to avoid http 404 ([#2185](https://github.com/Mailu/Mailu/issues/2185))
- Improved Documentation:  ([#2214](https://github.com/Mailu/Mailu/issues/2214))
- Deprecations and Removals: Remove POD_ADDRESS_RANGE in favor of SUBNET ([#1258](https://github.com/Mailu/Mailu/issues/1258))
- Misc:  ([#1341](https://github.com/Mailu/Mailu/issues/1341), [#2121](https://github.com/Mailu/Mailu/issues/2121), [#2211](https://github.com/Mailu/Mailu/issues/2211), [#2242](https://github.com/Mailu/Mailu/issues/2242), [#2338](https://github.com/Mailu/Mailu/issues/2338), [#2357](https://github.com/Mailu/Mailu/issues/2357), [#2383](https://github.com/Mailu/Mailu/issues/2383), [#2511](https://github.com/Mailu/Mailu/issues/2511), [#2526](https://github.com/Mailu/Mailu/issues/2526), [#2533](https://github.com/Mailu/Mailu/issues/2533), [#2539](https://github.com/Mailu/Mailu/issues/2539), [#2550](https://github.com/Mailu/Mailu/issues/2550), [#2566](https://github.com/Mailu/Mailu/issues/2566), [#2570](https://github.com/Mailu/Mailu/issues/2570), [#2577](https://github.com/Mailu/Mailu/issues/2577), [#2605](https://github.com/Mailu/Mailu/issues/2605), [#2606](https://github.com/Mailu/Mailu/issues/2606), [#2618](https://github.com/Mailu/Mailu/issues/2618), [#2634](https://github.com/Mailu/Mailu/issues/2634), [#2644](https://github.com/Mailu/Mailu/issues/2644), [#2660](https://github.com/Mailu/Mailu/issues/2660), [#2666](https://github.com/Mailu/Mailu/issues/2666), [#2692](https://github.com/Mailu/Mailu/issues/2692), [#2698](https://github.com/Mailu/Mailu/issues/2698), [#2704](https://github.com/Mailu/Mailu/issues/2704), [#2726](https://github.com/Mailu/Mailu/issues/2726), [#2733](https://github.com/Mailu/Mailu/issues/2733), [#2734](https://github.com/Mailu/Mailu/issues/2734))

Changelog
=========

For full details see the [releases page](https://mailu.io/1.9/releases.html)

Upgrade should run fine as long as you generate a new compose or stack configuration and upgrade your mailu.env. Please note that once you have upgraded to 1.9 you won't be able to roll-back to earlier versions without resetting user passwords.

If you use a reverse proxy in front of Mailu, it is vital to configure the newly introduced env variables REAL_IP_HEADER and REAL_IP_FROM.
These settings tell Mailu that the HTTP header with the remote client IP address from the reverse proxy can be trusted.
For more information see the [configuration reference](https://mailu.io/1.9/configuration.html#advanced-settings).

One major change for the docker compose file is that the antispam container needs a fixed hostname [#1837](https://github.com/Mailu/Mailu/issues/1837).
This is handled when you regenerate the docker compose file. A fixed hostname is required to retain rspamd history.

After changing mailu.env, it is required to recreate all containers for the changes to be propagated.

Please note that the shipped image for PostgreSQL database is fully deprecated now. To migrate to the official PostgreSQL image, you can follow our guide [here](https://mailu.io/master/database.html#mailu-postgresql)

1.9.0 - 2021-12-28
- Features: Document how to setup client autoconfig using an override ([#224](https://github.com/Mailu/Mailu/issues/224))
- Features: Add support for timezones ([#1154](https://github.com/Mailu/Mailu/issues/1154))
- Features: Ensure that RCVD_NO_TLS_LAST doesn't add to the spam score (as TLS usage can't be determined) ([#1705](https://github.com/Mailu/Mailu/issues/1705))
- Features: Add support for ECDSA certificates when letsencrypt is used. This means dropping compatibility for android < 4.1.1
  Add LETSENCRYPT_SHORTCHAIN to your configuration to avoid sending ISRG Root X1 (this will break compatibility with android < 7.1.1)
  Disable AUTH command on port 25
  Disable TLS tickets, reconfigure the cache to improve Forward Secrecy
  Prevent clear-text credentials from being sent to relays ([#1922](https://github.com/Mailu/Mailu/issues/1922))
- Features: Improved the SSO page. Warning! The new endpoints /sso and /static are introduced.
  These endpoints are now used for handling sign on requests and shared static files.
  You may want to update your reverse proxy to proxy /sso and /static to Mailu (to the front service).
  The example section of using a reverse proxy is updated with this information.
   - New SSO page is used for logging in Admin or Webmail.
   - Made SSO page available separately. SSO page can now be used without Admin accessible (ADMIN=false).
   - Introduced stub /static which is used by all sites for accessing static files.
   - Removed the /admin/ prefix to reduce complexity of routing with Mailu. Admin is accessible directly via /admin instead of /admin/ui
  Note: Failed logon attempts are logged in the logs of admin. You can watch this with fail2ban. ([#1929](https://github.com/Mailu/Mailu/issues/1929))
- Features: Make unbound work with ipv6
  Add a cache-min-ttl of 5minutes
  Enable qname minimisation (privacy) ([#1992](https://github.com/Mailu/Mailu/issues/1992))
- Features: Disable the login page if SESSION_COOKIE_SECURE is incompatible with how Mailu is accessed as this seems to be a common misconfiguration. ([#1996](https://github.com/Mailu/Mailu/issues/1996))
- Features: Derive a new subkey (from SECRET_KEY) for SRS ([#2002](https://github.com/Mailu/Mailu/issues/2002))
- Features: allow sending emails as user+detail@domain.tld ([#2007](https://github.com/Mailu/Mailu/issues/2007))
- Features: rspamd: get dkim keys via REST API instead of filesystem ([#2017](https://github.com/Mailu/Mailu/issues/2017))
- Features: updated roundcube to 1.5 and carddav to 4.2.2 using php8 ([#2035](https://github.com/Mailu/Mailu/issues/2035))
- Features: use dovecot-fts-xapian from alpine package ([#2072](https://github.com/Mailu/Mailu/issues/2072))
- Features: Make the rate limit apply to a subnet rather than a specific IP (/24 for v4 and /56 for v6) ([#116](https://github.com/Mailu/Mailu/issues/116))
- Features: Add instructions on how to create DNS records for email client auto-configuration (RFC6186 style) ([#224](https://github.com/Mailu/Mailu/issues/224))
- Features: Remove the Received header with PRIMARY_HOSTNAME [PUBLIC_IP] ([#466](https://github.com/Mailu/Mailu/issues/466))
- Features: Centralize the authentication of webmails behind the admin interface ([#783](https://github.com/Mailu/Mailu/issues/783))
- Features: Add sending quotas per user ([#1031](https://github.com/Mailu/Mailu/issues/1031))
- Features: Allow specific users to send emails from any address using the WILDCARD_SENDERS setting ([#1096](https://github.com/Mailu/Mailu/issues/1096))
- Features: Use semantic versioning for building releases.
  - Add versioning (tagging) for branch x.y (1.8). E.g. 1.8.0, 1.8.1 etc.
    - docker repo will contain x.y (latest) and x.y.z (pinned version) images.
    - The X.Y.Z tag is incremented automatically. E.g. if 1.8.0 already exists, then the next merge on 1.8 will result in the new tag 1.8.1 being used.
  - Make the version available in the image.
    -  For X.Y and X.Y.Z write the version (X.Y.Z) into /version on the image and add a label with version=X.Y.Z
  	  -  This means that the latest X.Y image shows the pinned version (X.Y.Z e.g. 1.8.1) it was based on. Via the tag X.Y.Z you can see the commit hash that triggered the built.
    -  For master write the commit hash into /version on the image and add a label with version={commit hash}
  -  Automatic releases. For x.y triggered builts (e.g. merge on 1.9) do a new github release for the pinned x.y.z (e.g. 1.9.2).
    -  Release shows a static message (see RELEASE_TEMPLATE.md) that explains how to reach the newsfragments folder and change the branch to the tag (x.y.z) mentioned in the release. Now you can get the changelog by reading all newsfragment files in this folder. ([#1182](https://github.com/Mailu/Mailu/issues/1182))
- Features: Add a credential cache to speedup authentication requests. ([#1194](https://github.com/Mailu/Mailu/issues/1194))
- Features: Introduces postfix logging via syslog with these features:
  - stdout logging still enabled
  - internal test request log messages (healthcheck) are filtered out by rsyslog
  - optional logging to file via POSTFIX_LOG_FILE env variable
  To use logging to file configure in mailu.env
  - ``POSTFIX_LOG_FILE``: The file to log the mail log to ([#1441](https://github.com/Mailu/Mailu/issues/1441))
- Features: Make smtp_tls_policy_maps easily configurable ([#1558](https://github.com/Mailu/Mailu/issues/1558))
- Features: Implement a language selector for the admin interface. ([#1567](https://github.com/Mailu/Mailu/issues/1567))
- Features: Add cli commands config-import and config-export ([#1604](https://github.com/Mailu/Mailu/issues/1604))
- Features: Implement SECRET_KEY_FILE and DB_PW_FILE variables for usage with Docker secrets. ([#1607](https://github.com/Mailu/Mailu/issues/1607))
- Features: Add possibility to enforce inbound STARTTLS via INBOUND_TLS_LEVEL=true ([#1610](https://github.com/Mailu/Mailu/issues/1610))
- Features: Refactor the rate limiter to ensure that it performs as intented. ([#1612](https://github.com/Mailu/Mailu/issues/1612))
- Features: Enable OCSP stapling for the http server within nginx. ([#1618](https://github.com/Mailu/Mailu/issues/1618))
- Features: Enable support of all hash types passlib supports. ([#1662](https://github.com/Mailu/Mailu/issues/1662))
- Features: Support configuring lz4 and zstd compression for dovecot. ([#1694](https://github.com/Mailu/Mailu/issues/1694))
- Features: Switch to bcrypt_sha256, replace PASSWORD_SCHEME with CREDENTIAL_ROUNDS and dynamically update existing hashes on first login ([#1753](https://github.com/Mailu/Mailu/issues/1753))
- Features: Implement AdminLTE 3 for the admin interface. ([#1764](https://github.com/Mailu/Mailu/issues/1764))
- Features: Implement MTA-STS and DANE validation. Introduce DEFER_ON_TLS_ERROR (default: True) to harden or loosen the policy enforcement. ([#1798](https://github.com/Mailu/Mailu/issues/1798))
- Features: Remove cyrus-sasl-plain as it's not packaged by alpine anymore. SASL-login is still available and used when relaying. ([#1851](https://github.com/Mailu/Mailu/issues/1851))
- Features: Hebrew translation has been completed. ([#1873](https://github.com/Mailu/Mailu/issues/1873))
- Features: Log authentication attempts on the admin portal ([#1926](https://github.com/Mailu/Mailu/issues/1926))
- Features: AdminLTE3 design optimizations, asset compression and caching

  - fixed copy of qemu-arm-static for alpine
  - added 'set -eu' safeguard
  - silenced npm update notification
  - added color to webpack call
  - changed Admin-LTE default blue
  - AdminLTE 3 style tweaks
  - localized datatables
  - moved external javascript code to vendor.js
  - added mailu logo
  - moved all inline javascript to app.js
  - added iframe display of rspamd page
  - updated language-selector to display full language names and use post
  - added fieldset to group and en/disable input fields
  - added clipboard copy buttons
  - cleaned external javascript imports
  - pre-split first hostname for further use
  - cache dns_* properties of domain object (immutable during runtime)
  - fixed and splitted dns_dkim property of domain object (space missing)
  - added autoconfig and tlsa properties to domain object
  - suppressed extra vertical spacing in jinja2 templates
  - improved accessibility for screen reader
  - deleted unused/broken /user/forward route
  - updated gunicorn to 20.1.0 to get rid of buffering error at startup
  - switched webpack to production mode
  - added css and javascript minimization
  - added pre-compression of assets (gzip)
  - removed obsolete dependencies
  - switched from node-sass to dart-sass
  - changed startup cleaning message from error to info
  - move client config to "my account" section when logged in ([#1966](https://github.com/Mailu/Mailu/issues/1966))
- Features: Remove Mailu PostgreSQL. It is fully deprecated. No images will be built anymore and it cannot be selected in the setup utility.
  The roundcube database flavour (e.g. PostgreSQL or SQLite) can now be selected indepently of the Mailu (Admin) database flavour.
  Fix bug #1838. ([#2069](https://github.com/Mailu/Mailu/issues/2069))
- Bugfixes: RELAYNETS should be a comma separated list of networks ([#360](https://github.com/Mailu/Mailu/issues/360))
- Bugfixes: Fix rate-limiting on /webdav/ ([#1194](https://github.com/Mailu/Mailu/issues/1194))
- Bugfixes: Fixed fetchmail losing track of fetched emails upon container recreation.
  The relevant fetchmail files are now retained in the /data folder (in the fetchmail image).
  See the docker-compose.yml file for the relevant volume mapping.
  If you already had your own mapping, you must double check the volume mapping and take action. ([#1223](https://github.com/Mailu/Mailu/issues/1223))
- Bugfixes: Ensure that the podop socket is always owned by the postfix user (wasn't the case when build using non-standard base images... typically for arm64) ([#1294](https://github.com/Mailu/Mailu/issues/1294))
- Bugfixes: Fix "extract_host_port" function to support containers with custom / dynamic ports ([#1669](https://github.com/Mailu/Mailu/issues/1669))
- Bugfixes: Fix CVE-2021-23240, CVE-2021-3156 and CVE-2021-23239 for postgresql
  by force-upgrading sudo. ([#1760](https://github.com/Mailu/Mailu/issues/1760))
- Bugfixes: Fix roundcube environment configuration for databases ([#1831](https://github.com/Mailu/Mailu/issues/1831))
- Bugfixes: Alpine has removed support for btree and hash in postfix... please use lmdb instead ([#1917](https://github.com/Mailu/Mailu/issues/1917))
- Bugfixes: Webmail and Radicale (webdav) were not useable with domains with special characters such as umlauts.
  Webmail and radicale now use punycode for logging in.
  Punycode was not used in the HTTP headers. This resulted in illegal non-ASCII HTTP headers. ([#1952](https://github.com/Mailu/Mailu/issues/1952))
- Bugfixes: Ensure that we do not trust the source-ip address set in headers if REAL_IP_HEADER isn't set. If you are using Mailu behind a reverse proxy, please ensure that you do read the documentation. ([#1960](https://github.com/Mailu/Mailu/issues/1960))
- Bugfixes: Reverse proxy documentation has been updated to reflect new security hardening from PR#1959.
  If you do not set the configuration parameters in Mailu what reverse proxy header to trust,
  then Mailu will not have access to the real ip address of the connecting client.
  This means that rate limiting will not properly work. You can also not use fail2ban.
  It is very important to configure this when using a reverse proxy. ([#1962](https://github.com/Mailu/Mailu/issues/1962))
- Bugfixes: Fixed roundcube sso login not working. ([#1990](https://github.com/Mailu/Mailu/issues/1990))
- Bugfixes: The DB_PORT and ROUNDCUBE_DB_PORT environment variables were not actually used. They are removed from the documentation. For using different ports you can already use the notation host:port . ([#2073](https://github.com/Mailu/Mailu/issues/2073))
- Bugfixes: Ensure that webmail tokens expire in sync with sessions ([#2080](https://github.com/Mailu/Mailu/issues/2080))
- Bugfixes: Introduce SESSION_TIMEOUT (1h) and PERMANENT_SESSION_LIFETIME (30d) ([#2094](https://github.com/Mailu/Mailu/issues/2094))
- Bugfixes: Hide the login of the user in sent emails ([#1638](https://github.com/Mailu/Mailu/issues/1638))
- Bugfixes: SSO login page to webmail did not work if WEB_WEBMAIL=/ was set. ([#2078](https://github.com/Mailu/Mailu/issues/2078))
- Bugfixes: #2079 Webmail token check does not work if WEBMAIL_ADDRESS is set to a hostname.
  #2081 Fix typo in nginx config for webmail port (10043 to 10143) ([#2079](https://github.com/Mailu/Mailu/issues/2079))
- Bugfixes: Alias, relay and fetchmail lists in the admin interface were missing the edit button. ([#2093](https://github.com/Mailu/Mailu/issues/2093))
- Bugfixes: Fix bug introduced by enhanced session management ([#2098](https://github.com/Mailu/Mailu/issues/2102))
- Bugfixes: Fix build dependencies postfix-mta-sts-resolver. ([#2106](https://github.com/Mailu/Mailu/issues/2106))
- Improved Documentation: Document hardware requirements when using clamav.
  Clamav requires **at least** 2GB of memory.
  This 2Gb does not entail any other software running on the box.
  So in total you require at least 3GB of memory and 1GB swap when antivirus is enabled. ([#470](https://github.com/Mailu/Mailu/issues/470))
- Improved Documentation: Added documentation for how to switch the database back-end used by Mailu.
  Added documentation for migrating from the deprecated Mailu PostgreSQL image to a different PostgreSQL database. ([#1037](https://github.com/Mailu/Mailu/issues/1037))
- Improved Documentation: Add documentation for Traefik 2 in Reverse Proxy ([#1503](https://github.com/Mailu/Mailu/issues/1503))
- Misc:  ([#1696](https://github.com/Mailu/Mailu/issues/1696), [#1712](https://github.com/Mailu/Mailu/issues/1712), [#1828](https://github.com/Mailu/Mailu/issues/1828), [#1830](https://github.com/Mailu/Mailu/issues/1830))


1.8.0 - 2021-08-06
--------------------

- Features: Update version of roundcube webmail and carddav plugin. This is a security update. ([#1841](https://github.com/Mailu/Mailu/issues/1841))
- Features: Update version of rainloop webmail to 1.16.0. This is a security update. ([#1845](https://github.com/Mailu/Mailu/issues/1845))
- Features: Changed default value of AUTH_RATELIMIT_SUBNET to false. Increased default value of the rate limit in setup utility (AUTH_RATELIMIT) to a higher value. ([#1867](https://github.com/Mailu/Mailu/issues/1867))
- Features: Update jquery used in setup. Set pinned versions in requirements.txt for setup. This is a security update. ([#1880](https://github.com/Mailu/Mailu/issues/1880))
- Bugfixes: Replace PUBLIC_HOSTNAME and PUBLIC_IP in "Received" headers to ensure that no undue spam points are attributed ([#191](https://github.com/Mailu/Mailu/issues/191))
- Bugfixes: Don't replace nested headers (typically in attached emails) ([#1660](https://github.com/Mailu/Mailu/issues/1660))
- Bugfixes: Fix letsencrypt access to certbot for the mail-letsencrypt flavour ([#1686](https://github.com/Mailu/Mailu/issues/1686))
- Bugfixes: Fix CVE-2020-25275 and CVE-2020-24386 by upgrading alpine for
  dovecot which contains a fixed dovecot version. ([#1720](https://github.com/Mailu/Mailu/issues/1720))
- Bugfixes: Antispam service now uses a static hostname. Rspamd history is only retained when the service has a fixed hostname. ([#1837](https://github.com/Mailu/Mailu/issues/1837))
- Bugfixes: Fix a bug preventing colons from being used in passwords when using radicale/webdav. ([#1861](https://github.com/Mailu/Mailu/issues/1861))
- Bugfixes: Remove dot in blueprint name to prevent critical flask startup error in setup. ([#1874](https://github.com/Mailu/Mailu/issues/1874))
- Bugfixes: fix punycode encoding of domain names ([#1891](https://github.com/Mailu/Mailu/issues/1891))
- Improved Documentation: Update fail2ban documentation to use systemd backend instead of filepath for journald ([#1857](https://github.com/Mailu/Mailu/issues/1857))
- Misc: Switch from client side (cookie) sessions to server side sessions and protect against session-fixation attacks. We recommend that you change your SECRET_KEY after upgrading. ([#1783](https://github.com/Mailu/Mailu/issues/1783))


v1.8.0rc - 2020-09-28
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
complete. Please note that the shipped image for PostgreSQL database will be
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
- Enhancement: Added webmail-imap dependency in docker compose ([#403](https://github.com/Mailu/Mailu/issues/403))
- Enhancement: Add environment variables to allow running outside of docker compose ([#429](https://github.com/Mailu/Mailu/issues/429))
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
