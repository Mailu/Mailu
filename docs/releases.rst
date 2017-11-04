Release notes
=============

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

- ``%@domain.tld`` will match any uncatched email sent to that domain (catch-all)
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
