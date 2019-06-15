.. _faq:

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
#. We use Travis-CI for some very basic building and testing;
#. The pull request needs to be code-reviewed and tested by at least two members
   from the contributors team.
  
Please consider that this project is mostly developed in people their free time.
We thank you for your understanding and patience.

I would like to donate (for a feature)
``````````````````````````````````````

Donations are welcome to the authors of the project directly, we do not manage any central
donation pot. Also, check the ``AUTHORS.md`` file for Patreon link or equivalent. If you
wish to contact a contributor specifically, please do so on `Matrix`_

.. _`Matrix`: https://matrix.to/#/#mailu:tedomum.net
.. _`open issues`: https://github.com/Mailu/Mailu/issues
.. _`new issue`: https://github.com/Mailu/Mailu/issues/new
.. _`Enhancement issues`: https://github.com/Mailu/Mailu/issues?q=is%3Aissue+is%3Aopen+label%3Atype%2Fenhancement
.. _`Feature request issues`: https://github.com/Mailu/Mailu/issues?q=is%3Aopen+is%3Aissue+label%3Atype%2Ffeature

Deployment related
------------------

What is the difference between DOMAIN and HOSTNAMES?
````````````````````````````````````````````````````

Similar questions:

- Changing domain doesn't work
- Do I need a certificate for ``DOMAIN``?

``DOMAIN`` is the main mail domain. Aka, server identification for outgoing mail. DMARC reports point to ``POSTMASTER`` @ ``DOMAIN``.
These are really the only things it is used for. You don't need a cert for ``DOMAIN``, as it is a mail domain only and not used as host in any sense.
However, it is usual that ``DOMAIN`` gets setup as one of the many mail domains. None of the mail domains ever need a certificate.
TLS certificates work on host connection level only.

``HOSTNAMES`` however, can be used to connect to the server. All host names supplied in this variable will need a certificate. When ``TLS_FLAVOR=letsencrypt`` is set,
a certificate is requested automatically for all those domains.

So when you have something like this:

.. code-block:: bash

  DOMAIN=example.com
  POSTMASTER=me
  HOSTNAMES=mail.example.com,mail.foo.com,bar.com
  TLS_FLAVOR=letsencrypt

- You'll end up with a DMARC address to ``me@example.com``.
- Server identifies itself as the SMTP server of ``@example.com`` when sending mail. Make sure your reverse DNS hostname is part of that domain!
- Your server will have certificates for the 3 hostnames. You will need to create ``A`` and ``AAAA`` records for those names,
  pointing to the IP addresses of your server.
- The admin interface generates ``MX`` and ``SPF`` examples which point to the first entry of ``HOSTNAMES`` but these are only examples.
  You can modify them to use any other ``HOSTNAMES`` entry.

You're mail service will be reachable for IMAP, POP3, SMTP and Webmail at the addresses:

- mail.example.com
- mail.foo.com
- bar.com

.. note::

  In this case ``example.com`` is not reachable as a host and will not have a certificate.
  It can be used as a mail domain if MX is setup to point to one of the ``HOSTNAMES``. However, it is possible to include ``example.com`` in ``HOSTNAMES``.

*Issue reference:* `742`_, `747`_.

How to make IPv6 work?
``````````````````````

Docker currently does not expose the IPv6 ports properly, as it does not interface with ``ip6tables``.
Lets start with quoting everything that's wrong:

  Unfortunately, initially Docker was not created with IPv6 in mind.
  It was added later and, while it has come a long way, is still not as usable as one would want.
  Much discussion is still going on as to how IPv6 should be used in a containerized world;
  See the various GitHub issues linked below:
  
  - Giving each container a publicly routable address means all ports (even unexposed / unpublished ports) are suddenly
    reachable by everyone, if no additional filtering is done
    (`docker/docker#21614 <https://github.com/docker/docker/issues/21614>`_)
  - By default, each container gets a random IPv6, making it impossible to do properly do DNS;
    the alternative is to assign a specific IPv6 address to each container,
    still an administrative hassle (`docker/docker#13481 <https://github.com/docker/docker/issues/13481>`_)
  - Published ports won't work on IPv6, unless you have the userland proxy enabled
    (which, for now, is enabled by default in Docker)
  - The userland proxy, however, seems to be on its way out
    (`docker/docker#14856 <https://github.com/docker/docker/issues/14856>`_) and has various issues, like:
  
    - It can use a lot of RAM (`docker/docker#11185 <https://github.com/docker/docker/issues/11185>`_)
    - Source IP addresses are rewritten, making it completely unusable for many purposes, e.g. mail servers 
      (`docker/docker#17666 <https://github.com/docker/docker/issues/17666>`_),
      (`docker/libnetwork#1099 <https://github.com/docker/libnetwork/issues/1099>`_).
  
  -- `Robbert Klarenbeek <https://github.com/robbertkl>`_ (docker-ipv6nat author)

So, how to make it work? Well, by using `docker-ipv6nat`_! This nifty container will set up ``ip6tables``,
just as Docker would do for IPv4. We know that nat-ing is not advised in IPv6,
however exposing all containers to public network neither. The choice is ultimately yous.

Mailu `setup utility`_ generates a safe IPv6 ULA subnet by default. So when you run the following command,
Mailu will start to function on IPv6:

.. code-block:: bash

  docker run -d --restart=always -v /var/run/docker.sock:/var/run/docker.sock:ro --privileged --net=host robbertkl/ipv6nat

.. _`docker-ipv6nat`: https://github.com/robbertkl/docker-ipv6nat
.. _`setup utility`: https://setup.mailu.io

How does Mailu scale up?
````````````````````````

Recent works allow Mailu to be deployed in Docker Swarm and Kubernetes.
This means it can be scaled horizontally. For more information, refer to :ref:`kubernetes`
or the `Docker swarm howto`_.

*Issue reference:* `165`_, `520`_.

How to achieve HA / failover?
`````````````````````````````

The mailboxes and databases for Mailu are kept on the host filesystem under ``$ROOT/``.
For making the **storage** highly available, all sorts of techniques can be used:

- Local raid-1
- btrfs in raid configuration
- Distributed network filesystems such as GlusterFS or CEPH

Note that no storage HA solution can protect against incidental deletes or file corruptions.
Therefore it is advised to create backups on a regular base!

A backup MX can be configured as **failover**. For this you need a separate server running
Mailu. On that server, your domains will need to be setup as "Relayed domains", pointing
to you main server. MX records for the mail domains with a higher priority number will have
to point to this server. Please be aware that a backup MX can act as a `spam magnet`_.

For **service** HA, please see: `How does Mailu scale up?`_


*Issue reference:* `177`_, `591`_.

.. _`spam magnet`: https://blog.zensoftware.co.uk/2012/07/02/why-we-tend-to-recommend-not-having-a-secondary-mx-these-days/

Does Mailu run on Rancher?
``````````````````````````

There is a rancher catalog for Mailu in the `Mailu/Rancher`_ repository. The user group for Rancher is small,
so we cannot promise any support on this when you're heading into trouble. See the repository README for more details.

*Issue reference:* `125`_.

.. _`Mailu/Rancher`: https://github.com/Mailu/Rancher


Can I run Mailu without host iptables?
``````````````````````````````````````

When disabling iptables in docker, its forwarding proxy process takes over.
This creates the situation that every incoming connection on port 25 seems to come from the
local network (docker's 172.17.x.x) and is accepted. This causes an open relay!

For that reason we do **not** support deployment on Docker hosts without iptables.

*Issue reference:* `332`_.

How can I override settings?
````````````````````````````

Postfix, Dovecot, Nginx and Rspamd support overriding configuration files. Override files belong in
``$ROOT/overrides``. Please refer to the official documentation of those programs for the
correct syntax. The following file names will be taken as override configuration:

- `Postfix`_ - ``postfix.cf``;
- `Dovecot`_ - ``dovecot.conf``;
- `Nginx`_ - All ``*.conf`` files in the ``nginx`` sub-directory.
- `Rspamd`_ - All files in the ``rspamd`` sub-directory.

*Issue reference:* `206`_.

I want to integrate Nextcloud 15 (and newer) with Mailu
````````````````````````````````````````

1. Enable External user support from Nextcloud Apps interface

2. Configure additional user backends in Nextcloud’s configuration config/config.php using the following syntax if you use at least Nextcloud 15.

.. code-block:: bash

  <?php

  /** Use this for Nextcloud 15 and newer **/
  'user_backends' => array(
      array(
          'class' => 'OC_User_IMAP',
          'arguments' => array(
            '127.0.0.1', 993, 'ssl', 'example.com', true, false
        ),
      ),
  ),
  

If a domain name (e.g. example.com) is specified, then this makes sure that only users from this domain will be allowed to login.
After successfull login the domain part will be striped and the rest used as username in NextCloud. e.g. 'username@example.com' will be 'username' in NextCloud. You can disable this behaviour by changing true (the fifth parameter) to false. 

*Issue reference:* `575`_.

I want to integrate Nextcloud 14 (and older) with Mailu
````````````````````````````````````````

1. Install dependencies required to authenticate users via imap in Nextcloud

.. code-block:: bash

  apt-get update \
   && apt-get install -y libc-client-dev libkrb5-dev \
   && rm -rf /var/lib/apt/lists/* \
   && docker-php-ext-configure imap --with-kerberos --with-imap-ssl \
   && docker-php-ext-install imap

2. Enable External user support from Nextcloud Apps interface

3. Configure additional user backends in Nextcloud’s configuration config/config.php using the following syntax for Nextcloud 14 (and below):

.. code-block:: bash

  <?php

  /** Use this for Nextcloud 14 and older **/
  'user_backends' => array(
      array(
          'class' => 'OC_User_IMAP',
          'arguments' => array(
              '{imap.example.com:993/imap/ssl}', 'example.com'
          ),
      ),
  ),

If a domain name (e.g. example.com) is specified, then this makes sure that only users from this domain will be allowed to login.
After successfull login the domain part will be striped and the rest used as username in NextCloud. e.g. 'username@example.com' will be 'username' in NextCloud.

*Issue reference:* `575`_.

.. _`Postfix`: http://www.postfix.org/postconf.5.html
.. _`Dovecot`: https://wiki.dovecot.org/ConfigFile
.. _`NGINX`:   https://nginx.org/en/docs/
.. _`Rspamd`:  https://www.rspamd.com/doc/configuration/index.html

.. _`Docker swarm howto`: https://github.com/Mailu/Mailu/tree/master/docs/swarm/master
.. _`125`: https://github.com/Mailu/Mailu/issues/125
.. _`165`: https://github.com/Mailu/Mailu/issues/165
.. _`177`: https://github.com/Mailu/Mailu/issues/177
.. _`332`: https://github.com/Mailu/Mailu/issues/332
.. _`742`: https://github.com/Mailu/Mailu/issues/742
.. _`747`: https://github.com/Mailu/Mailu/issues/747
.. _`520`: https://github.com/Mailu/Mailu/issues/520
.. _`591`: https://github.com/Mailu/Mailu/issues/591
.. _`575`: https://github.com/Mailu/Mailu/issues/575

Technical issues
----------------

In this section we are trying to cover the most common problems our users are having.
If your issue is not listed here, please consult issues with the `troubleshooting tag`_.

Changes in .env don't propagate
```````````````````````````````

Variables are sent to the containers at creation time. This means you need to take the project
down and up again. A container restart is not sufficient.

.. code-block:: bash

  docker-compose down && \
  docker-compose up -d

*Issue reference:* `615`_.

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

How do I activate DKIM and DMARC?
`````````````````````````````````
Go into the Domain Panel and choose the Domain you want to enable DKIM for.
Click the first icon on the left side (domain details).
Now click on the top right on the *"Regenerate Keys"* Button.
This will generate the DKIM and DMARC entries for you.

*Issue reference:* `102`_.

Do you support Fail2Ban?
````````````````````````

Fail2Ban is not included in Mailu. Fail2Ban needs to modify the host's IP tables in order to
ban the addresses. We consider such a program should be run on the host system and not
inside a container. The ``front`` container does use authentication rate limiting to slow
down brute force attacks.

We *do* provide a possibility to export the logs from the ``front`` service to the host.
For this you need to set ``LOG_DRIVER=journald`` or ``syslog``, depending on the log
manager of the host. You will need to setup the proper Regex in the Fail2Ban configuration.
Be aware that webmail authentication appears to come from the Docker network,
so don't ban those addresses!

*Issue reference:* `85`_, `116`_, `171`_, `584`_, `592`_.

Users can't change their password from webmail
``````````````````````````````````````````````

All users have the abilty to login to the admin interface. Non-admin users
have only restricted funtionality such as changing their password and the
spam filter weight settings.

*Issue reference:* `503`_.

rspamd: DNS query blocked on multi.uribl.com
````````````````````````````````````````````

This usually relates to the DNS server you are using. Most of the public servers block this query or there is a rate limit.
In order to solve this, you most probably are better off using a root DNS resolver, such as `unbound`_. This can be done in multiple ways:

- Use the *Mailu/unbound* container. This is an optional include when generating the ``docker-compose.yml`` file with the setup utility.
- Setup unbound on the host and make sure the host's ``/etc/resolve.conf`` points to local host.
  Docker will then forward all external DNS requests to the local server.
- Set up an external DNS server with root resolving capabilities.

In any case, using a dedicated DNS server will improve the performance of your mail server.

*Issue reference:* `206`_, `554`_, `681`_.

Is there a way to support more (older) ciphers?
```````````````````````````````````````````````

See `How can I override settings?`_ .
You will need to add the protocols you wish to support in an override for the ``front`` container (Nginx).

.. code-block:: bash

  ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
  ssl_ciphers <list of ciphers>;

We **strongly** advice against downgrading the TLS version and ciphers!

*Issue reference:* `363`_, `698`_.

.. _`troubleshooting tag`: https://github.com/Mailu/Mailu/issues?utf8=%E2%9C%93&q=label%3Afaq%2Ftroubleshooting
.. _`85`: https://github.com/Mailu/Mailu/issues/85
.. _`102`: https://github.com/Mailu/Mailu/issues/102
.. _`116`: https://github.com/Mailu/Mailu/issues/116
.. _`171`: https://github.com/Mailu/Mailu/issues/171
.. _`206`: https://github.com/Mailu/Mailu/issues/206
.. _`363`: https://github.com/Mailu/Mailu/issues/363
.. _`426`: https://github.com/Mailu/Mailu/issues/426
.. _`503`: https://github.com/Mailu/Mailu/issues/503
.. _`554`: https://github.com/Mailu/Mailu/issues/554
.. _`584`: https://github.com/Mailu/Mailu/issues/584
.. _`592`: https://github.com/Mailu/Mailu/issues/592
.. _`615`: https://github.com/Mailu/Mailu/issues/615
.. _`681`: https://github.com/Mailu/Mailu/pull/681
.. _`698`: https://github.com/Mailu/Mailu/issues/698
.. _`unbound`: https://nlnetlabs.nl/projects/unbound/about/

A user gets ``Sender address rejected: Access denied. Please check the`` ``message recipient […] and try again`` even though the sender is legitimate?
``````````````````````````````````````````````````````````````````````````````````````````````````````````````````````````````````````````````````````
First, check if you are really sure the user is a legitimate sender, i.e. the registered user is authenticated successfully and own either the account or alias he/she is trying to send from. If you are really sure this is correct, then the user might try to errornously send via port 25 insteadof the designated SMTP client-ports. Port 25 is meant for server-to-server delivery, while users should use port 587 or 465.
