Changelog
=========

Notable changes to this project are documented in the current file. For more
details about individual changes, see the Git log. You should read this before
upgrading Freposte.io as some changes will include useful notes.

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
