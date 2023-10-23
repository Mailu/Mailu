Release notes
=============

Mailu 2.0 - 2023-04-03
----------------------

Mailu 2.0 is finally available. It is vital to read the `Upgrading` section before upgrading to Mailu 2.0 as it introduces major features and breaking changes from 1.9.

The Helm Chart project will be updated soon after this release.

The Mailu project has moved to ghcr.io for hosting the docker images. The images on docker.io will be taken down after this release.

Highlights
``````````

This is an overview of the major features introduced in Mailu 2.0.

Multi-arch images (ARM support)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Mailu project now ships multi-arch images for the architectures:

- linux/amd64.
- linux/arm64/v8.
- linux/arm/v7.

It is now possible to run Mailu on most ARM hardware such as the Raspberry Pi.

Auto-configuration for client
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

On the domain details page, there are new DNS records for enabling DNS auto-client configuration.
Provided they are configured, email clients will make use of them to auto-configure.

If a reverse proxy is in use, settings might have to be tweaked.

For Apple users, the client setup page now offers an autoconfiguration link to automatically configure
their device.

RESTFul API
^^^^^^^^^^^

Mailu offers a RESTful API for changing the Mailu configuration.
Now, anything that can be configured via the Mailu web administration interface
can also be configured via the Mailu RESTful API.

Configuring a new domain or add new users can be fully automated now.

The current API makes use of a single API token for authentication.
In a future release this will likely be re-visited.

For more information refer to the :ref:`Mailu RESTful API <mailu_restful_api>` page.

Header authentication support (use external identity providers)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is now possible to use different authentication systems (such as keycloak, authentik, vouch-proxy) to handle the authentication of Mailu users.
This can be used to enable Single Sign On from other IDentity Providers via protocols such as OIDC or SAML2.

For more information see :ref:`Header authentication using an external proxy <header_authentication>` in the configuration reference.

Better anti-spoofing protection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Previously Mailu would reject emails where an attacker spoofs the envelope-From. Now Mailu also checks the header-From for any hosted domain.
It won't let any email which pretends to be for any of the local domains through unless they pass DMARC. This means that if you intend on sending emails for a domain hosted on the Mailu instance to the Mailu instance from somwhere else, you must setup DMARC.

Implement a password policy
^^^^^^^^^^^^^^^^^^^^^^^^^^^

In line with security best practices from `NIST (Special Publication 800-63B) <https://pages.nist.gov/800-63-3/sp800-63b.html#5111-memorized-secret-authenticators>`_, we have introduced a password policy.

Passwords now need to:

- be at least 8 characters long.
- not be listed on `HaveIBeenPwned <https://haveibeenpwned.com/Passwords>`_.


Significant improvements to the Rate-limiter
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Now the rate limiter will only take distinct attempts into account. We have two different types of checks:

- to prevent crendential bruteforce (an attacker trying to guess a password), we limit the maximal amount of attempts an attacker has for a given account (from any IP address).
- to prevent password spraying (an attacker trying the same common password on all accounts he can enumerate), we limit the maximal number of non-existing accounts an attacker can attempt to authenticate against from a given network subnet.

We have also implemented state-of-the-art features such as `Device Cookies <https://owasp.org/www-community/Slow_Down_Online_Guessing_Attacks_with_Device_Cookies>`_ and IP-whitelisting post-authentication to ensure we don't lock genuine users out.

Rate-limiters have a bad name because they are often misunderstood. If you have used Mailu's rate-limiter in the past and had a bad experience please consider giving it another try after upgrading.

Remember the login URL
^^^^^^^^^^^^^^^^^^^^^^

Mailu will now remember which URL was requested and redirect you to it post-authentication.

This functionality can be used by visiting a "deep" URL E.g.

- https://test.mailu.io/admin
- https://test.mailu.io/webmail

This results in a login page with a single login button. To access the normal login page, visit the root url.

- https://test.mailu.io

Users who only use the /admin endpoint can now bookmark https://test.mailu.io/admin. When logging in, it is possible to use the `Enter` key again to login (this will not login the webmail but admin).

Introduction of SnappyMail
^^^^^^^^^^^^^^^^^^^^^^^^^^

The Rainloop webmail client has been replaced with SnappyMail.
The Rainloop project has multiple long outstanding security bugs. For this reason the Mailu project looked for alternatives.
SnappyMail is a fork of Rainloop focussed on performance and security. It offers a similar experience as Rainloop.

Do not mark spam as read
^^^^^^^^^^^^^^^^^^^^^^^^

In the user settings it is now possible to configure if a received spam email must be marked as read.
It is possible to see if you received spam now.

OLETools
^^^^^^^^

`OLETools <https://github.com/decalage2/oletools>`_ is introduced to block bad macros in Microsoft Office documents. OLETools is able to scan Microsoft Office documents and determine if a macro is malicous.

By default attachments with know bad/executable file extensions (such as ``.exe``) are blocked. See the FAQ for more information on updating the list of blocked file extensions.

New override system for Rspamd
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The override system for Rspamd has been overhauled. While the config files were first completely overridden, they are now merged.
Now overrides are placed in the location (in the Rspamd/Antispam container) /overrides.

If you use your own map files, change the location to ``/overrides/myMapFile.map`` in the corresponding conf file.
For example when overriding multimap.conf that use a custom ``.map`` file:

.. code-block:: bash

  #multimap.conf
  LOCAL_BL_DOMAIN {
    type = "from";
    filter = "email:domain";
    map = "/overrides/blacklist.map";
    score = 15;
    description = "Senders domain part is on the local blacklist";
    group = "local_bl";
  }

It works as following.

* If the override file overrides a Mailu defined config file,
  it will be included in the Mailu config file with lowest priority.
  This means it will merge with existing sections.

* If the override file does not override a Mailu defined config file,
  then the file will be placed in the rspamd local.d folder.
  It will merge with existing sections.

For more information, see the description of the local.d folder on the rspamd website:
https://www.rspamd.com/doc/faq.html#what-are-the-locald-and-overrided-directories


Add a button to the roundcube interface that gets you back to the admin interface
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Small feature, but so handy. The menu in Roundcube now shows a button to go the the web administration interface.
As a user you can now go back to your profile page where you can change your password or spam settings. And then go back to Roundcube again.

PROXY PROTOCOL Support
^^^^^^^^^^^^^^^^^^^^^^

Reverse proxies can connect to Mailu with the `proxy protocol <https://www.haproxy.org/download/1.8/doc/proxy-protocol.txt>`_ for HTTP and Mail. Below is a small example for Traefik connecting via proxy protocol to Mailu

.. code-block:: bash

  # Static configuration
  providers:
  file:
    directory: "/opt/traefik/conf"

  entryPoints:
    mailu-web:
      # Listen on port 8081 for incoming requests
      address: :443
    mailu-smtp:
      address: :25
    mailu-imaps:
      address: :993
    mailu-smtps:
      address: :465
    mailu-starttls:
      address: :587

  # From dynamic configuration /opt/traefik/conf
  tls:
    certificates:
      - certFile: /etc/letsencrypt/live/mydomain.com/fullchain.pem
        keyFile: /etc/letsencrypt/live/mydomain.com/privkey.pem

  tcp:
    routers:
      mailu-web:
        entryPoints:
          - mailu-web
        rule: "HostSNI(`*`)"
        service: "mailu-web"
      mailu-smtp:
        entryPoints:
          - mailu-smtp
        rule: "HostSNI(`*`)"
        service: "mailu-smtp"
      mailu-imaps:
        entryPoints:
          - mailu-imaps
        rule: "HostSNI(`*`)"
        service: "mailu-imaps"
      mailu-smtps:
        entryPoints:
          - mailu-smtps
        rule: "HostSNI(`*`)"
        service: "mailu-smtps"
      mailu-starttls:
        entryPoints:
          - mailu-starttls
        rule: "HostSNI(`*`)"
        service: "mailu-starttls"
    services:
      mailu-web:
        loadBalancer:
          proxyProtocol:
            version: 2
          servers:
            - address: "MailuServer:443"
      mailu-smtp:
        loadBalancer:
          proxyProtocol:
            version: 2
          servers:
            - address: "MailuServer:25"
      mailu-smtps:
        loadBalancer:
          proxyProtocol:
            version: 2
          servers:
            - address: "MailuServer:465"
      mailu-starttls:
        loadBalancer:
          proxyProtocol:
            version: 2
          servers:
            - address: "MailuServer:587"
      mailu-imaps:
        loadBalancer:
          proxyProtocol:
            version: 2
          servers:
            - address: "MailuServer:993"

Security hardening
^^^^^^^^^^^^^^^^^^

We have gone further than ever. Now Mailu containers drop their privileges and communicate on separate networks. They also share the same base image where on x86 `a Hardened memory allocator <https://github.com/GrapheneOS/hardened_malloc>`_ is configured.

Webmails relying on PHP now make use of `Snuffleupagus <https://github.com/jvoisin/snuffleupagus>`_.


New Functionality & Improvements
````````````````````````````````

For a list of all the changes (including bug fixes) refer to `CHANGELOG.md` in the root folder of the Mailu github project.

A short summary of the other new features:

- Features: Allow other folders to be synced by fetchmail.
- Features: Update the webmail images.
  Roundcube:

    - Switch to base image (alpine).
    - Switch to php-fpm.

  SnappyMail:

    - Switch to base image.
    - Upgrade php7 to php8.

- Features: Add FETCHMAIL_ENABLED to toggle the fetchmail functionality in the admin interface.
- Features: Create a polite and turtle delivery queue to accommodate destinations that expect emails to be sent slowly.
- Features: Add support for custom NGINX config in /etc/nginx/conf.d.
- Features: Configurable default spam threshold used for new users.
- Features: Create a GUI for WILDCARD_SENDERS.
- Features: Prevent signups with accounts for which an SQL-LIKE alias exists.
- Features: Introduce TLS_PERMISSIVE, a new advanced setting to harden cipher configuration on port 25. Changing the default is strongly discouraged, please read the documentation before doing so.
- Features: Implement the required glue to make "doveadm -A" work.
- Features: Drop postfix rsyslog localhost messages with IPv6 address.
- Features: Improved IPv6 support.
- Features: Provide a changelog for minor releases. The github release will now:

  * Provide the changelog message from the newsfragment of the PR that triggered the backport.
  * Provide a github link to the PR/issue of the PR that was backported.

- Enhance CI/CD workflow with retry functionality. All steps for building images are now automatically
  retried. If a build temporarily fails due to a network error, the retried step will still succeed.
- Features: Add Czech translation for web administration interface.


Upgrading
`````````

Upgrade should run fine as long as you generate a new compose & mailu.env and then reapply custom config settings to mailu.env.
Carefully read the :ref:`configuration page <common_cfg>` to check what old settings have been removed. If a setting is not listed anymore
on the :ref:`configuration page <common_cfg>`, then this setting has been removed.

If you use Fail2Ban, then the Fail2Ban intructions have been improved. It is **mandatory** to remove your Fail2Ban config
and re-apply it using the instructions from :ref:`updated Fail2Ban documentation <Fail2Ban>`.

If you use overrides for Rspamd, then please note that overrides are now placed in the location ``/overrides`` in the rspamd container.
If you use your own map files, change the location to ``/overrides/myMapFile.map`` in the corresponding rspamd conf file.

To use the new autoconfig endpoint and Mailu RESTFul API, you may need to update your reverse proxy config.
If you use ``TLS_FLAVOR=letsencrypt``, add autoconfig.myhostname.com to the setting ``HOSTNAMES=`` in mailu.env to generate a certificate for the autoconfig endpoint as well.
After starting your Mailu deployment, please refer to the section `DNS client auto-configuration entries` on the domain details page
in the web administration interface for the exact name of the autoconfig endpoint (https://test.mailu.io/admin/domain/details/test.mailu.io).

It is also recommended to have a look at :ref:`mta-sts <mta-sts>`.
When mta-sts is enabled, modern email servers will immediately use TLS for delivering emails to Mailu.

Mailu 1.9 - 2021-12-29
----------------------

Mailu 1.9 is available now.
Please see the section `Upgrading` for important information in regard to upgrading to Mailu 1.9.

Highlights
````````````````````````````````

Quite a lot of new features have been implemented. Of these new features we'd like to highlight these:

Security
^^^^^^^^

A fair amount of work went in this release; In no particular order:

- outbound SMTP connections from Mailu are now enjoying some protection against active attackers thanks to DANE and MTA-STS support. Specific policies can be configured for specific destinations thanks to ``tls_policy_maps`` and configuring your system to publish a policy has been documented in the FAQ.
- outbound emails can now be rate-limited (to mitigate SPAM in case an account is taken over)
- long term storage of passwords has been rethought to enable stronger protection against offline attackers (switch to iterated and salted SHA+bcrypt) while enabling much better performance (credential cache). Please encourage your users to use tokens where appropriate and keep in mind that existing hashes will be converted on first use to the new format.
- session handling has been reworked from the grounds up: they have been switched from client side (cookies) to server-side, unified (SSO, expiry, lifetime) across all web-facing applications and some mitigations against session fixation have been implemented.
- rate limiting has seen many improvements: It is now deployed on all entry points (SMTP/IMAP/POP3/WEB/WEBMAIL) and configured to defeat both password bruteforces (thanks to a limit against total number of failed attempts against an account over a period) and password spraying (thanks to a limit for each client on the total number of non-existing accounts that can be queried). Exemption mechanisms have been put in place (device tokens, dynamic IP whitelists) to ensure that genuine clients and users won't be affected by default and the default configuration thought to fit most use-cases.
- if you use letsencrypt, Mailu is now configured to offer both RSA and ECC certificates to clients; It will OSCP staple its replies where appropriate


Updated Admin interface
^^^^^^^^^^^^^^^^^^^^^^^

The Web Administration interface makes use of AdminLTE. The AdminLTE2 technology has been upgraded to AdminLTE3. This cost a lot of effort due to the changes between AdminLTE2 and AdminLTE3.
As a result the webpage looks more modern. All tables now have a filter and columns that can be sorted. If you have many users or domains, this will be a very welcome new feature!

A language selector has been added. On the login page and in the Web Admin Interface, the language selector can be accessed in the top right.


Import/Export command on steroids
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Mailu command line has been enhanced with the new config-export and config-import command.
**Everything** that can be configured in the Mailu Web Administration Interface can now be exported and imported via yaml files.
So via YAML files, you can now bulk configure a complete new installation, without the need to access the Mailu Web Administration Interface.

It is also possible to create new users or import new users (with password hashes) using the config-import.

With this new command it is very easy to switch to a different database management system for the Mailu database. Simply dump your configuration to yaml file.
After setting up your new Mailu system with the different DBMS, you can import the yaml file with all Mailu configuration.

For more information, see the :ref:`Mailu command line <config-export>` page.


New SSO login page
^^^^^^^^^^^^^^^^^^

A new single sign on login page is introduced which handles logins for the Mailu Web Administration Interface and webmail. It has enabled a drastic attack-surface reduction and will enable us to add support for two factor authentication in the future.

All failed login attempts are now logged to the Admin service, significantly simplifying the deployment of solutions such as Fail2ban.

See the :ref:`updated Fail2Ban documentation <Fail2Ban>` for more information.


Semantic versioning
^^^^^^^^^^^^^^^^^^^

From Mailu 1.9, we will use semantic versioning. First we only had x.y (e.g. 1.9) releases. For every update to an existing version, we will create an additional x.y.z (e.g. 1.9.1) release.

- The X.Y (1.9) tag will always feature the latest version.
- The X.Y.Z (1.9.1) tag is a pinned version. This release is not updated. You can use this to update in a controlled manner. At a convenient time, you can choose to switch to a newer version (e.g 1.9.2). The X.Y.Z tag is incremented automatically when an update is pushed for the X.Y release.

The images now also contain the release it was built for.

- Every docker image will have a docker label with the version.
- Every docker image will have the file /version with the same version information.
- Master images will contain the commit hash that initiated the built of the image.
- X.Y and X.Y.Z images will have the X.Y.Z version that triggered the built.

On the github project we will automatically create releases for each X.Y.Z release. Via this release you can check what commit hash the tag is assigned to.

With this improvement in our CI/CD workflow, it is possible to be notified when an update is released via github releases. It is also possible to use pinned versions to update in a controlled manner.


New Functionality & Improvements
````````````````````````````````

For a list of all the changes (including bug fixes) refer to `CHANGELOG.md` in the root folder of the Mailu github project.

A short summary of the new features:

- Roundcube and Rainloop have been updated.
- All dependencies have been updated to the latest security update
- AdminLTE (used by Admin service) is updated to AdminLTE3.
- Much improved rate limiting.

  - Rate limiting small subnets instead of single IP addresses.
  - Rate limiting for accounts that do not exist.
  - Rate limiting for existing accounts (failed logon attempts).
  - Device-tokens are introduced to ensure genuine users are not locked out

- Domain details page is enhanced with DNS client auto-configuration (RFC6186) entries.
- Centralize the authentication of webmails behind the admin interface.

   - The new single sign on page opens up the possibility to introduce 2 factor authentication in the future.

- Add sending quotas per user (configured in mailu.env). This determines how many emails each user can send every day.
- Allow specific users to send emails from any address using the WILDCARD_SENDERS setting (mailu.env.).
- Use semantic versioning for building releases.
- Internal improvements to improve performance of authentication requests.
- Introduced a language selector for the Admin interface.
- Add cli commands config-import and config-export for importing/exporting Mailu config via YAML.
- Enable support of all hash types passlib supports.
- Switch to bcrypt_sha256 (stronger hashing of passwords in Mailu database)/
- Introduce MTA-STS and DANE validation.
- Added Hebrew translation.
- Log authentication attempts on the admin portal. Fail2ban can now be used to monitor login attempts on Admin/Webmail.
- Remove Mailu PostgreSQL.
- Admin/Webmail sessions expire now. This can be tweakers via mailu.env.


Upgrading
`````````

Upgrade should run fine as long as you generate a new compose or stack configuration and upgrade your mailu.env. Please note that once you have upgraded to 1.9 you won't be able to roll-back to earlier versions without resetting user passwords.

If you use a reverse proxy in front of Mailu, it is vital to configure the newly introduced environment variables `REAL_IP_HEADER`` and `REAL_IP_FROM`.
These settings tell Mailu that the HTTP header with the remote client IP address from the reverse proxy can be trusted.
For more information see the :ref:`configuration reference <reverse_proxy_headers>`.

If you use Fail2Ban, you configure Fail2Ban to monitor failed logon attempts for the web-facing frontend (Admin/Webmail). See the :ref:`updated Fail2Ban documentation <Fail2Ban>` for more information.

Please note that the shipped image for the PostgreSQL database is fully deprecated now.
To migrate to the official PostgreSQL image, you can follow our :ref:`migration guide <migrate_mailu_postgresql>`.


Mailu 1.8 - 2021-08-7
---------------------

The full 1.8 release is finally ready. There have been some changes in the contributors team. Many people from the contributors team have stepped back due to changed priorities in their life.
We are very grateful for all their contributions and hope we will see them back again in the future.
This is the main reason why it took so long for 1.8 to be fully released.

Fortunately more people have decided to join the project. Some very nice contributions have been made which will become part of the next 1.9 release.
We hope that future Mailu releases will be released more quickly now we have more active contributors again.

For a list of all changes refer to `CHANGELOG.md` in the root folder of the Mailu github project. Please read the 'Override location changes' section further on this page. It contains important information for the people who use the overrides folder.

New Functionality & Improvements
````````````````````````````````

Here’s a short summary of new features:

- Roundcube and Rainloop have been updated.
- All dependencies have been updated to the latest security update.
- Fail2ban documentation has been improved.
- Switch from client side (cookie) sessions to server side sessions and protect against session-fixation attacks. We recommend that you change your SECRET_KEY after upgrading.
- Full-text-search is back after having been disabled for a while due to nasty bugs. It can still be disabled via the mailu.env file.
- Tons of documentation improvements, especially geared towards new users.
- (Experimental) support for different architectures, such as ARM.
- Improvements around webmails, such as CardDAV, GPG and a new skin for an updated roundcube, and support for MySQL for it. Updated Rainloop, too.
- Improvements around relaying, such as AUTH LOGIN and non-standard port support.
- Update to alpine:3.14 as baseimage for most containers.
- Setup warns users about compose-IPv6 deployments which have caused open relays in the past.
- Improved handling of upper-vs-lowercase aliases and user-addresses.
- Improved rate-limiting system.
- Support for SRS.
- Japanese localisation is now available.


Upgrading
`````````

Upgrade should run fine as long as you generate a new compose or stack
configuration and upgrade your mailu.env.

Please note that the shipped image for PostgreSQL database is deprecated.
The shipped image for PostgreSQL is not maintained anymore from release 1.8.
We recommend switching to an external PostgreSQL image as soon as possible.

Override location changes
^^^^^^^^^^^^^^^^^^^^^^^^^

If you have regenerated the Docker compose and environment files, there are some changes to the configuration overrides.
Override files are now mounted read-only into the containers. The Dovecot and Postfix overrides are moved in their own sub-directory. If there are local override files, they will need to be moved from ``overrides/`` to ``overrides/dovecot`` and ``overrides/postfix/``.

Recreate SECRET_KEY after upgrading
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Improvements have been made to protect again session-fixation attacks.
To be fully protected, it is required to change your SECRET_KEY in Mailu.env after upgrading.
A new SECRET_KEY is generated when you recreate your docker-compose.yml & mailu.env file via setup.mailu.io.

The SECRET_KEY is an uppercase alphanumeric string of length 16. You can manually create such a string via
```cat /dev/urandom | tr -dc 'A-Z0-9' | fold -w ${1:-16} | head -n 1```

After changing mailu.env, it is required to recreate all containers for the changes to be propagated.

Update your DNS SPF Records
^^^^^^^^^^^^^^^^^^^^^^^^^^^

It has become known that the SPF DNS records generated by the admin interface are not completely standard compliant anymore. Please check the DNS records for your domains and compare them to what the new admin-interface instructs you to use. In most cases, this should be a simple copy-paste operation for you ….

Fixed hostname for antispam service
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For history to be retained in Rspamd, the antispam container requires a static hostname. When you re-generate your docker-compose.yml file (or helm-chart), this will be covered.


Mailu 1.8rc - 2020-10-02
------------------------

Release 1.8 has come a long way again. Due to corona the project slowed down to a crawl. Fortunately new contributors have joined the team what enabled us to still release Mailu 1.8 this year.

Please note that the current 1.8 is what we call a "soft release": It’s there for everyone to see and use, but to limit possible user-impact of this very big release, it’s not yet the default in the setup-utility for new users. When upgrading, please treat it with some care, and be sure to always have backups!

For a list of all changes refer to `CHANGELOG.md` in the root folder of the Mailu github project. Please read the 'Override location changes' section. It contains important information for the people who use the overrides folder.

New Functionality & Improvements
````````````````````````````````

Here’s a short summary of new features:

- Full-text-search is back after having been disabled for a while due to nasty bugs. It can still be disabled via the mailu.env file.
- Tons of documentation improvements, especially geared towards new users.
- (Experimental) support for different architectures, such as ARM.
- Improvements around webmails, such as CardDAV, GPG and a new skin for an updated roundcube, and support for MySQL for it. Updated Rainloop, too.
- Improvements around relaying, such as AUTH LOGIN and non-standard port support.
- Update to alpine:3.12 as baseimage for most containers.
- Setup warns users about compose-IPv6 deployments which have caused open relays in the past.
- Improved handling of upper-vs-lowercase aliases and user-addresses.
- Improved rate-limiting system.
- Support for SRS.
- Japanese localisation is now available.

Upgrading
`````````

Upgrade should run fine as long as you generate a new compose or stack
configuration and upgrade your mailu.env.

Please note that the shipped image for PostgreSQL database is deprecated.
The shipped image for PostgreSQL is not maintained anymore from release 1.8.
We recommend switching to an external PostgreSQL database as soon as possible.

Override location changes
^^^^^^^^^^^^^^^^^^^^^^^^^

If you have regenerated the Docker compose and environment files, there are some changes to the configuration overrides.
Override files are now mounted read-only into the containers. The Dovecot and Postfix overrides are moved in their own sub-directory. If there are local override files, they will need to be moved from ``overrides/`` to ``overrides/dovecot`` and ``overrides/postfix/``.

Update your DNS SPF Records
^^^^^^^^^^^^^^^^^^^^^^^^^^^

It has become known that the SPF DNS records generated by the admin interface are not completely standard compliant anymore. Please check the DNS records for your domains and compare them to what the new admin-interface instructs you to use. In most cases, this should be a simple copy-paste operation for you ….


Mailu 1.7 - 2019-08-22
----------------------

Release 1.7 has come a long way and was really expected after the project first
saw a slowdown in contributions around january then a wave of new contributors
and contributions.

New functionality
`````````````````

Most changes are internal, main features include:

- the admin UI now properly displaying on mobile
- relays supporting authentication thanks to new settings
- ability to create an initial admin user using environment variables

Other changes include software updates with some new features in Rainloop
1.30.0.

Back-end
````````

One of the big tasks was upgrading to latest Alpine (3.10), which is now finished.
Also, a lot was improved about the environment variables meant to provide
specific hosts in custom setups.

Finally, among many bug fixes and discrete enhancements, we removed most static
assets from the repository and now build the admin UI dynamically using
Webpack.

Localization
````````````

The localization effort move to a hosted Weblate, that you can access at the
following uri: https://translate.tedomum.net/projects/mailu/admin/

Please have a look and help translate Mailu into your home tongue.

Upgrading
`````````

Upgrade should run fine as long as you generate a new compose or stack
configuration and upgrade your mailu.env.

If you run the PostgreSQL server, the database was upgrade, so you will need to
dump the database before upgrading and load the dump after the upgrade is
complete. Please note that the shipped image for PostgreSQL database will be
deprecated before 1.8.0, you can switch to an external database server by then.


Mailu 1.6 - 2019-01-18
----------------------

Its been more than a year since the release of 1.5! And what a year it has been...
More then 800 commits are done since 1.5, containing thousands of additions.
We had the honor of welcoming more and more contributors and we actually established
a dedicated team of trusted contributors.

With new review guidelines we now allow the project to grow without dependence
on any single person. And thus merging pull requests at much shorter time.
On top of that we finally got around to creating a simple test suite on TravisCI,
which is doing some e-mail sending and receiving. This greatly helps the reviewing process.

For a complete overview of changes, see our `changelog`_.
Here we'll try to give you the highlights.

.. _`changelog`: https://github.com/Mailu/Mailu/blob/master/CHANGELOG.md

New functionality
`````````````````

We offer a lot new functions in the user experience. Some of the highlights would be quota
support from the admin interface, optional user sign up with recaptcha, auto-reply start date,
and a client setup page.

Mailu now also offers a `setup utility`_.
This utility helps users to generate a `docker-compose.yml` and `mailu.env` through guided steps.

Documentation
`````````````

Quite some efforts were done in expanding the documentation of Mailu.
We've added support for :ref:`kubernetes`, `Docker Swarm`_ and a :ref:`faq` section.
There is now also a section on running the Mailu web interfaces behind :ref:`traefik_proxy`.

We now also Dockerized the documentation, allowing for easy local running and versions
management on our web server.

.. _`Docker Swarm`: https://github.com/Mailu/Mailu/blob/master/docs/swarm/master/README.md

Back-end
````````

Lots and lots of hours went in to the back-end. Work on numerous bugs,
increased the general performance and allowing for better maintainability.

We've reworked the complete interface with the database. All queries are now done
through the Admin container, with that being the single point of contact with the
database. Now we also support the usage of MySQL and PostgreSQL databases and Mailu
comes with its own PostgreSQL image! This allows for Mailu to be used in larger scaled
operations.

Main software versions
``````````````````````
- Alpine 3.8.2
- Python 3.6.6
- SQLite 3.25.3
- Postfix 3.3.0
- Dovecot 2.3.2.1
- Radicale 2.1.10
- Rspamd 1.7.6
- ClamAV 0.100.2
- Nginx 1.14.2
- Rainloop 1.12.1
- Roundcube 1.3.8
- Fetchmail 6.3.26
- Unbound 1.7.3
- Postgresql 10.5

Upgrading
`````````

We've done some pretty intrusive works on the DB migrations scripts. Although thoroughly
tested, we would recommend users to create a backup copy of ``/mailu/data/main.db`` somewhere.

Use the `setup utility`_ to obtain new ``docker-compose.yml`` and ``mailu.env`` files.
For this upgrade it is necessary to bring the project down and up, due to network definition changes:

.. code-block:: bash

  docker compose pull
  docker compose down --remove-orphans
  docker compose up -d

After everything runs successfully, ``/mailu/certs/dhparam.pem`` is no longer needed and can be deleted.
It's included in the Mailu distribution by default now. Also the old ``.env`` can be deleted.

.. _`setup utility`: https://setup.mailu.io

Mailu 1.5 - 2017-11-05
----------------------

It has been two years since this project started, one year since it was renamed
to Mailu and took a more serious path toward building a proper email server
distribution. The experience has been extremely interesting and we as
contributors should be quite proud of what was accomplished in that time.

Mailu started as a random project of administration interface for Postfix, it
is now running thousands of mail servers, has reached over half a million pulls
on Docker hub and contributions from very different and frankly interesting
people.

Version 1.5 is about bringing the features that were intended for the late
version 2.0. It includes many new concepts like:

- alternative domains, a way to configure a domain that is semantically
  equivalent to another;
- domain relays, a way to relay emails to a separate server;
- authentication tokens, a way to let users generate passwords for their various
  clients and restrict authentication per IP address.

The release also includes some structural changes to the project. Nginx is now
the main frontend container and terminates all connections, performing
TLS and authentication directly. Letsencrypt support is now more complete,
with various TLS "flavors" for all kinds of setup.

Finally, a big change about how versions are managed: the ``stable`` branch
will be deprecated with the end of branch ``1.4``. Mailu will now only publish
branches per version, as any version jump requires manual updates anyway. This
will avoid confusion about which branch is currently considered *the* stable
one. End of support for branches will happen after 2 version changes (e.g.
end of support for branch ``1.4`` will happen when branch ``1.6`` is released).
Finally, intermediary versions backporting some important features will be
branched as subversions first (branch ``1.5.1`` for instance), then merge in
the branch version once enough testing has happened.

More details about the changes are available in the `changelog`_, and this
release will be followed by a short-term upgrade including some more features
and bug fixes.

**If you are upgrading**, please go through the setup guide and download the
latest ``docker-compose.yml`` and ``.env``, then update them with your
specific settings, because more than 50% of these templates was rewritten.
You should then be able to pull and start your new e-mail stack with
no issue, simply remove orphaned container, since some were renamed and others
were removed (e.g. rmilter):

.. code-block:: bash

  docker compose pull
  docker compose up -d --remove-orphans

If you experience problems when upgrading, feel free to post issues and contact
us on our chat channel for emergency support.

Regarding statistics, Mailu has gone from "no tracker at all" to a tracker that
we find is designed to preserve privacy and security as much as possible. Your
admin container will now perform DNS requests for a domain that we hold,
including information about your "instance id" (a unique and random string)
and Mailu version. If your mail server performs direct DNS queries instead
of going through a DNS recursor, you might want to opt-out of statistics if
you would prefer the server IP address not be included anywhere (we do not log
it, but our hosting provider might). This can be accomplished in the ``.env``
file directly.

.. _`changelog`: https://github.com/Mailu/Mailu/blob/master/CHANGELOG.md

Mailu 1.3 - 2016-11-06
----------------------

**First a warning as TL;DR. Following the project rename, please read
the migration guide carefully if you were already running Freeposte.**

Renaming the project was a critical step in its life and we
certainly hope that it will help gain even more traction and collaborate
every day to add new features and improve Mailu.

This new release introduces mostly bugfixes and a couple of enhancements.
It was however the most complicated to prepare and publish because we had
to deal for the first time with multiple active contributors, sometimes
diverging points of view, a solid user base that would prefer their production
not break, and some major upstream issues.

The release itself was delayed a month, partly due to these changes, partly due
to upstream issues. One of them for instance, a bug in Dovecot, took us a
couple of long nights debugging low-level memory management code in Dovecot in
order to fix the vacation message in Mailu! This lead to humble contributions
to Dovecot and Alpine Linux and we are still proud to be contributing to a
larger software environment.

Among the major changes that we introduced, Rainloop is now officially
supported as a Webmail and we are open to contributions to add even more
alternatives to the next release.

Also, Mailu admin interface now has built-in internationalization and we will
initiate a localization campaign to add at least French and German to the list
of supported languages. Please contact us if you would like to contribute
another translation.

Finally, we hardened Postfix configuration both for security reasons
(preventing address usurpation upon existing SPF) and to prevent spam. We
found that the already effective antispam filter now blocks more that 99% of
junk messages on our test servers.

A more detailed list of changes is available in the project changelog.

Please read the `Setup Guide`_
if you plan on setting up a new mail server. Mailu is free software,
you are more than welcome to report issues, ask for features or enhancements,
or contribute your own modifications!

Freeposte.io 1.2 - 2016-08-28
-----------------------------

The past few weeks have been very productive thanks to multiple contributors
and reporters. A hundred commits later, Freeposte.io release 1.2 is ready.

Most changes in the release are security-related: we eventually added CSRF
checks, applied most security best practices including TLS hardening based
on the great documentation by `BetterCrypto`_,
and started a discussion about how the mail server stack should be
secure-by-default while maintaining as many features as possible.

Additional great change is the new ability to declare catch-all aliases and
wildcard aliases in general.

When creating an alias, one may now enable the "SQL LIKE" syntax then use
standard SQL wildcards ``%`` and ``_`` to specify matches for a given alias.
For instance :

- ``%@domain.tld`` will match any uncaught email sent to that domain (catch-all)
- ``support-%@domain.tld`` will match any email sent to an address starting with
  ``support-``
- ``_@domain.tld`` will match any email sent to a one-character address
- ``co_tact@domain.tld`` will match both ``contact@domain.tld`` and
  ``comtact@domain.tld`` along will all other combinations to make up for
  any usual typing mistake.

Finally, the update process changed with Freeposte.io 1.2: you do not have to
manually setup an installed branch anymore. Instead, you may simply use the
default ``docker-compose.yml`` file and the ``:latest`` tag that will now
point to the latest *stable* version. Those who know what they are doing and
still want to use continuous builds from the Git repository may switch to the
``:testing`` Docker images.

A more detailed list of changes is available in the project changelog.

Please read the `Setup Guide`_
if you plan on setting up a new mail server. Freeposte.io is free software,
you are more than welcome to report issues, ask for features or enhancements,
or contribute your own modifications!

.. _`BetterCrypto`: https://bettercrypto.org/

Freeposte.io 1.1 - 2016-07-31
-----------------------------

When we started the Freeposte.io adventure back in December, we weren't quite
sure the project would lead to anything but a bunch of scripts to manage our
mail server at `TeDomum`_.

About 6 month later, we have got word from a dozen individuals and half a
dozen nonprofits that have started setting up Freeposte.io or are using it
for production emails. All mailboxes at TeDomum have been running on top
of Freeposte.io for the past 5 months and happily received thousands of emails.

Release 1.0 was definitely not ready for production: the anti-spam services
were unstable, lots of junk messages still got through, there was still no
support for outgoing DKIM and thus no way to properly setup DMARC. These
have been addressed and we are really enthusiastic about releasing 1.1 and
expecting some feedback and contributions.

Please read the `Setup Guide`_
if you plan on setting up a new mail server. Freeposte.io is free software,
you are more than welcome to report issues, ask for features or enhancements,
or even contribute your own modifications!

.. _`TeDomum`: https://tedomum.net
.. _`Setup Guide`: https://github.com/kaiyou/freeposte.io/wiki/Setup-Guide
