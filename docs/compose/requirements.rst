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
system agnostic.

Because most of our tests run on Debian stable, we recommend
one of these for the base system. Mailu should however be able to run on
any of the `officially supported distributions`_.

For the purpose of this guide, all examples are based on Debian stable. The
differences with other system will however hardly be noticeable.

.. _`officially supported distributions`: https://docs.docker.com/engine/installation/

Install the distribution
------------------------

First, install Debian stable from the *netinstall* CD image. When installing,
make sure that you either:

 - setup a root *ext4* partition,
 - or setup a root *btrfs* partition,
 - or leave enough unpartitioned space for a dedicated *ext4* or *btrfs*
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
``443``, ``465``, ``587``, ``993``, ``995`` nor ``4190`` as these are used by Mailu
services. Therefore, you should disable or uninstall any program that is
listening on these ports (or have them listen on a different port), and make sure
that these ports are open in your firewall if you have one. For instance, on a
default Debian install:

.. code-block:: bash

  apt-get autoremove --purge exim4 exim4-base


Finally, Docker relies heavily on ``iptables`` for port forwarding. You
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

Additionally, you must install ``docker compose`` v2 by following the instructions
from the `Docker website`_ if you plan on using the Compose flavor. Compose is a
management tool for Docker, especially suited for multiple containers systems
like Mailu.

.. _`detailed instructions`: https://docs.docker.com/engine/installation/
.. _`Docker website`: https://docs.docker.com/compose/

Once everything is setup, you should be able to run the following commands
(exact version numbers do not matter):

.. code-block:: bash

  $ docker version
    Client: Docker Engine - Community
     Version:           20.10.22
     API version:       1.41
     Go version:        go1.18.9
     Git commit:        3a2c30b
     Built:             Thu Dec 15 22:27:03 2022
     OS/Arch:           linux/arm64
     Context:           default
     Experimental:      true

    Server: Docker Engine - Community
     Engine:
      Version:          20.10.22
      API version:      1.41 (minimum version 1.12)
      Go version:       go1.18.9
      Git commit:       42c8b31
      Built:            Thu Dec 15 22:25:25 2022
      OS/Arch:          linux/arm64
      Experimental:     false
     containerd:
      Version:          1.6.14
      GitCommit:        9ba4b250366a5ddde94bb7c9d1def331423aa323
     runc:
      Version:          1.1.4
      GitCommit:        v1.1.4-0-g5fd4c4d
     docker-init:
      Version:          0.19.0
      GitCommit:        de40ad0

  $ docker compose version
    Docker Compose version v2.14.1
