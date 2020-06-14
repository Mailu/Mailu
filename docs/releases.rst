Release notes
=============

Mailu 1.8 - tbd
----------------------

Override location changes
`````````````````````````

If you have regenerated the Docker compose and environment files, there are some changes to the configuration overrides.
Override files are now mounted read-only into the containers. The Dovecot and Postfix overrides are moved in their own sub-directory. If there are local override files, they will need to be moved from ``overrides/`` to ``overrides/dovecot`` and ``overrides/postfix/``.

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

One of the big tasks was upgradig to latest Alpine (3.10), which is now finished.
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
complete. Please not that the shipped image for PostgreSQL database will be
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

  docker-compose pull
  docker-compose down --remove-orphans
  docker-compose up -d

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
sepcific settings, because more than 50% of these templates was rewritten.
You should then be able to pull and start your new e-mail stack with
no issue, simply remove orphaned container, since some were renamed and others
were removed (e.g. rmilter):

.. code-block:: bash

  docker-compose pull
  docker-compose up -d --remove-orphans

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
