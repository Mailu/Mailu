Frequently asked questions
==========================

Informational
-------------

Where to ask questions?
```````````````````````

First, please read this FAQ to check if your question is listed here.
Simple questions best fit in our `Matrix`_ room.
For more complex questions, you can always open a `new issue`_ on GitHub.
We actively monitor the issues list.


My installation is broken!
``````````````````````````

We're sorry to hear that. Please check for common mistakes and troubleshooting
advice in the `Technical issues`_ section of this page.

I think I found a bug!
``````````````````````

If you did not manage to solve the issue using this FAQ and there is not any 
`open issues`_ describing the same problem, you can continue to open a
`new issue`_ on GitHub.

I want a new feature or enhancement!
````````````````````````````````````

Great! We are always open for suggestions. We currently maintain two tags:

- `Enhancement issues`_: Typically used for optimization of features in the project.
- `Feature request issues`_: For implementing new functionality,
  plugins and applications.

Please check if your idea (or something similar) is already mentioned there.
If there is one open, you can choose to vote with a thumbs up, so we can
estimate the popular demand. Please refrain from writing comments like
*"me too"* as it clobbers the actual discussion.

If you can't find anything similar, you can open a `new issue`_.
Please also share (where applicable):

- Use case: how does this improve the project?
- Any research done on the subject. Perhaps some links to upstream website,
  reference implementations etc.

Why does my feature/bug take so long to solve?
``````````````````````````````````````````````

You should be aware that creating, maintaining and expanding a mail server
distribution requires a lot of effort. Mail servers are highly exposed to hacking attempts,
open relay scanners, spam and malware distributors etc. We need to work in a safe way and
have to prevent pushing out something quickly.

**TODO: Move the next section into the contributors part of docs**
We currently maintain a strict work flow:

#. Someone writes a solution and sends a pull request;
#. We use Travis-CI fore some very basic building and testing;
#. The pull request needs to be code-reviewed and tested by at least two members
   from the contributors team.
  
Please consider that this project is mostly developed in people their free time.
We thank you for your understanding and patience.

I would like to donate (for a feature)
``````````````````````````````````````

Donations are welcome at the `patreon`_ account of the project lead. It will be used to pay
for infra structure and project related costs. If there are leftovers, it will be distributed
among the developers.

It is not yet possible to pay for a specific feature. We don't have
any bounty system implemented. Feel free to come with suggestions in
our ongoing `project management`_ discussion issue.


.. _`Matrix`: https://matrix.to/#/#mailu:tedomum.net
.. _`open issues`: https://github.com/Mailu/Mailu/issues
.. _`new issue`: https://github.com/Mailu/Mailu/issues/new
.. _`Enhancement issues`: https://github.com/Mailu/Mailu/issues?q=is%3Aissue+is%3Aopen+label%3Atype%2Fenhancement
.. _`Feature request issues`: https://github.com/Mailu/Mailu/issues?q=is%3Aopen+is%3Aissue+label%3Atype%2Ffeature
.. _`patreon`: https://patreon.com/kaiyou
.. _`project management`: https://github.com/Mailu/Mailu/issues/508

Deployment related
------------------

Technical issues
----------------

Changes in .env don't propagate
```````````````````````````````

Variables are sent to the containers at creation time. This means you need to take the project
down and up again. A container restart is not sufficient.

.. code-block:: bash

  docker-compose down && \
  docker-compose up -d

*Issue reference:* `615`_,

TLS certificate issues
``````````````````````

When there are issues with the TLS/SSL certificates, Mailu denies service on secure ports.
This is a security precaution. Symptoms are:

- 403 browser errors;

These issues are typically caused by four scenarios:

#. ``TLS_FLAVOR=notls`` in ``.env``;
#. Certificates expired;
#. When ``TLS_FLAVOR=letsencrypt``, it might be that the *certbot* script is not capable of
   obtaining the certificates for your domain. See `letsencrypt issues`_
#. When ``TLS_FLAVOR=certs``, certificates are supposed to be copied to ``/mailu/certs``.
   Using an external ``letsencrypt`` program, it tends to happen people copy the whole
   ``letsencrypt/live`` directory containing symlinks. Symlinks do not resolve inside the
   container and therefore it breaks the TLS implementation.

letsencrypt issues
..................

In order to determine the exact problem on TLS / Let's encrypt issues, it might be helpful
to check the logs.

.. code-block:: bash

  docker-compose logs front | less -R
  docker-compose exec front less /var/log/letsencrypt/letsencrypt.log

Common problems:

- Port 80 not reachable from outside.
- Faulty DNS records: make sure that all ``HOSTNAMES`` have **A** (IPv4) and **AAAA** (IPv6)
  records, pointing the the ``BIND_ADDRESS4`` and ``BIND_ADDRESS6``.
- DNS cache not yet expired. It might be that old / faulty DNS records are stuck in a cache
  en-route to letsencrypt's server. The time this takes is set by the ``TTL`` field in the
  records. You'll have to wait at least this time after changing the DNS entries.
  Don't keep trying, as you might hit `rate-limits`_.

.. _`rate-limits`: https://letsencrypt.org/docs/rate-limits/

Copying certificates
....................

As mentioned above, care must be taken not to copy symlinks to the ``/mailu/certs`` location.

**The wrong way!:**

.. code-block:: bash

  cp -r /etc/letsencrypt/live/domain.com /mailu/certs

**The right way!:**

.. code-block:: bash

  mkdir -p /mailu/certs
  cp /etc/letsencrypt/live/domain.com/privkey.pem /mailu/certs/key.pem
  cp /etc/letsencrypt/live/domain.com/fullchain.pem /mailu/certs/cert.pem

See also :ref:`external_certs`.

*Issue reference:* `426`_, `615`_.


WIP: Link to `troubleshooting`_ related issues will be in the bottom of this section.

.. _`426`: https://github.com/Mailu/Mailu/issues/426
.. _`615`: https://github.com/Mailu/Mailu/issues/615
.. _`troubleshooting`: https://github.com/Mailu/Mailu/issues?utf8=%E2%9C%93&q=label%3Afaq%2Ftroubleshooting
