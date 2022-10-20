Docker compose requirements
===========================

Hardware considerations
-----------------------

You should make sure that your hardware (virtual or physical) is compatible with
the latest Linux kernel. The minimal required memory and swap are:

* When using antivirus (clamav):

  * 3GB of memory

  * 1GB of swap

* When not using antivirus (clamav):

  * 1GB of memory

  * 1GB of swap


Pick a distribution
-------------------

The mail server runs as a set of Docker containers, so it is almost operating 
system agnostic as long as a fairly recent Linux kernel is running and 
the Docker API (>= 1.11) is available.

Because most of our tests run on Debian Jessie and Debian Stretch, we recommend
one of these for the base system. Mailu should however be able to run on
any of the `officially supported distributions`_.

For the purpose of this guide, all examples are based on Debian Stretch. The
differences with other system will however hardly be noticeable.

.. _`officially supported distributions`: https://docs.docker.com/engine/installation/

Install the distribution
------------------------

First, install Debian Stretch from the *netinstall* CD image. When installing,
make sure that you either:

 - setup a root *ext4* partition,
 - or setup a root *btrfs* partition,
 - or leave enough unpartitionned space for a dedicated *ext4* or *btrfs*
   partition.

If you chose to create a dedicated partition, simply mount it to
``/var/lib/docker``. You could also create a separate partition (*ext4* is a
sane default) and mount it to ``/mailu`` for storing e-mail data.

Docker supports *AUFS* over *ext4* and *btrfs* as stable storage drivers.
Other filesystems are supported such as *OverlayFS*. If you know what you are
doing, you should go for it.

Mailu uses Docker port forwarding from the host to make services
available to external users. First, your host should have a public IP address
configured (see ``/etc/network/interfaces``) or your router should
forward connections to its internal IP address. Due to spam problems and
reputation services, it is highly recommended that you use a dedicated IP 
address for your mail server and that you have a dedicated hostname 
with forward and reverse DNS entries for this IP address.

Also, your host must not listen on ports ``25``, ``80``, ``110``, ``143``,
``443``, ``465``, ``587``, ``993`` or ``995`` as these are used by Mailu
services. Therefore, you should disable or uninstall any program that is
listening on these ports (or have them listen on a different port). For
instance, on a default Debian install:

.. code-block:: bash

  apt-get autoremove --purge exim4 exim4-base


Finally, Docker relies heavily on ``iptables`` for port forwardings. You
should use ``iptables-persistent`` (or any equivalent tool on other
systems) for managing persistent rules. If you were brave enough to switch to
``nftables``, you will have to rollback until official support is released
by Docker or setup your own rulesets.

Install Docker
--------------

Mailu relies on some of the latest Docker features. Therefore, you should
install Docker from the official repositories instead of your distribution
ones.

The Docker website is full of `detailed instructions`_
about setting up a proper Docker install. Default configuration should be
suited for Mailu.

Additionally, you must install ``docker-compose`` by following the instructions
from the `Docker website`_ if you plan on using the Compose flavor. Compose is a
management tool for Docker, especially suited for multiple containers systems
like Mailu.

.. _`detailed instructions`: https://docs.docker.com/engine/installation/
.. _`Docker website`: https://docs.docker.com/compose/

Once everything is setup, you should be able to run the following commands
(exact version numbers do not matter):

.. code-block:: bash

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
