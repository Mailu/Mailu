Installing Freeposte.io
=======================

Things to consider
==================

Freeposte.io is working, it has been powering hundreds of e-mail accounts
since around January 2016. It is still not massively tested however and
you should not run any critical mail server until you have properly tested
every feature.

Also, the idea behind Freeposte.io is based on the work by folks from Poste.io.
If free software is not the reason you chose Freeposte.io or if you are seeking
long-term professional support, you should probably turn to them instead.

Picking a distribution
======================

The mail server runs as a set of Docker containers. It is thus almost agnostic
of the underlying operating system as long as a fairly recent Linux kernel is
running and the Docker API (>= 1.11) is available.

Because most of our tests run on Debian Jessie and Debian Stretch, we recommend
one of these for the base system. Freeposte.io should however be able to run on
any of the [officially supported distributions](https://docs.docker.com/engine/installation/).

For the purpose of this guide, all examples are based on Debian Stretch. The
differences with other system will hardly be noticeable however.

Setting up the distribution
===========================

First, install Debian Stretch from the *netinstall* CD image. When installing,
make sure that you either:

 - setup a root *ext4* partition,
 - or setup a root *btrfs* partition,
 - or leave enough unpartitionned space for a dedicated *ext4* or *btrfs*
   partition.

If you chose to create a dedicated partition, simply mount it to
``/var/lib/docker``. You could also create a separate partition (*ext4* is a
sane default)  ans mount it to ``/freeposte`` for storing e-mail data.

Docker supports *AUFS* over *ext4* and *btrfs* as stable storage drivers.
Other filesystems are supported such as *OverlayFS*. If you know what you are
doing, you should go for it.

Freeposte.io uses Docker port forwarding from the host to make services
available to external users. First, your host should have a public IP address
configured (see ``/etc/network/interfaces``) or your router should
forward connections to its internal IP address. Due to spam problems and
reputation services, it
is highly recommended that you use a dedicated IP address for your mail server
and that you have a dedicated hostname with forward and reverse DNS entries
for this IP address.

Also, your host must not listen on ports ``25``, ``80``, ``110``, ``143``,
``443``, ``465``, ``587``, ``993`` or ``995`` as these are used by Freeposte
services. Therefore, you should disable or uninstall any program that is
listening on these ports (or have them listen on a different port). For
instance, on a default Debian install:

```
apt-get autoremove --purge exim4 exim4-base
```

Finally, Docker relies heavily on ``iptables`` for port forwardings. You
should use ``iptables-persistent`` (or any equivalent tool on other
systems) for managing persistent rules. If you were brave enough to switch to
``nftables``, you will have to rollback until official support is released
by Docker or setup your own rulesets.

Setting up Docker
=================

Freeposte.io relies on some of the latest Docker features. Therefore, you should
install Docker from the official repositories instead of your distribution
ones.

The Docker website is full of [detailed instructions](https://docs.docker.com/engine/installation/)
about setting up a proper Docker install. Default configuration should be
suited for Freeposte.io.

Additionally, you must install ``docker-compose`` by following the instructions
from the [Docker website](https://docs.docker.com/compose/). Compose is a
management tool for Docker, especially suited for multiple containers systems
like Freeposte.io.

Once everything is setup, you should be able to run the following commands
(exact version numbers do not matter):

```
$ docker version
Client:
 Version:      1.11.2
 API version:  1.23
 Go version:   go1.6.2
 Git commit:   b9f10c9
 Built:        Sun Jun  5 23:17:55 2016
 OS/Arch:      linux/amd64

Server:
 Version:      1.11.1
 API version:  1.23
 Go version:   go1.6.2
 Git commit:   5604cbe
 Built:        Mon May  2 00:06:51 2016
 OS/Arch:      linux/amd64

$ docker-compose version
docker-compose version 1.7.1, build 6c29830
docker-py version: 1.8.1
CPython version: 3.5.1
OpenSSL version: OpenSSL 1.0.2h  3 May 2016
```

Preparing the mail server environment
=====================================

Freeposte.io will store all of its persistent data in ``/freeposte`` by default,
simply create the directory and move there:

```
mkdir /freeposte
cd /freeposte
```

Docker Compose configuration is stored in a file named ``docker-compose.yml``.
Additionally, Freeposte.io relies on an environment file for various settings.

Download the templates files from the git repository:

```
wget https://raw.githubusercontent.com/kaiyou/freeposte.io/master/docker-compose.yml
wget https://raw.githubusercontent.com/kaiyou/freeposte.io/master/freeposte.env
```

These templates are used for development environment. So, if you do not plan
on building Freeposte.io from source, simply remove the ``build:`` references:

```
sed -i '/build:/d' docker-compose.yml
```

The default configuration will pull the latest image built from the Docker
Hub, which is based on the latest commit on GitHub. This behaviour is ok for
evaluating Freeposte.io, but you should at least specify a branch. You will
still get bugfixes and security updates, but breaking changed will not be
pulled unless you explicitely change the branch number. To specify you want
to pull the ``1.0`` branch, simply add the version number to the ``image``
field:

```
VERSION=1.0
sed -i "/image:/s/\(:[0-9.]*\)\?$/:$VERSION/" docker-compose.yml
```

You should always have all containers using the same branch.

Finally, edit the ``freeposte.env`` file and update the following settings:

 - set ``DEBUG`` to ``False`` unless your are debugging,
 - set ``SECRET_KEY`` to a random 16 bytes string,
 - set ``DOMAIN`` to your main mail domain,
 - set ``ADMIN`` to the local part of the admin address on the main domain,
 - set ``HOSTNAME`` to your mailserver hostname.

Setting up certificates
=======================

Freeposte.io relies heavily on TLS and must have a key pair and a certificate
available, at least for the hostname configured in ``freeposte.env``.

Create the certificate directory:

```
mkdir /freeposte/certs
```

Then create two files in this directory:

 - ``cert.pem`` contains the certificate,
 - ``key.pem`` contains the key pair.

Creating the first admin user
=============================

Freeposte.io does not come with any default user. You have to create the
first admin user manually. First, start the mail server stack:

```
docker-compose up -d
```

Then create the admin user:

```
docker exec -i -t freeposte_admin_1 python manage.py admin admin exmaple.net admin
```

This will create ``admin@example.net`` with password ``admin``. Connect to
the Web admin interface change the password to a strong one:

```
https://your-host-name.tld/admin/
```

Testing before going live
=========================

You should test all the critical features before using the mail server for
actual messages. Try to send and receive e-mails, monitor the logs for some
unexpected errors, etc.

Your server should now be running!
