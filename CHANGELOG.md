Changelog
=========

Notable changes to this project are documented in the current file. For more
details about individual changes, see the Git log. You should read this before
upgrading Freposte.io as some changes will include useful notes.

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
