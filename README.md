Freeposte.io
============

Simple yet functional and full-featured mail server as a set of Docker images.
The idea behing Freeposte.io is identical to motivations that led to poste.io:
providing a simple and maintainable mail server that is painless to manage and
does not require more resources than necessary.

People from poste.io did an amazing job at accomplishing this ; any company
looking for a serious yet simple mail server with professional support should
turn to them.

This project is meant for free software supporters and hackers to reach the
same level of functionality and still be able to host a complete mail server
at little cost while running only FOSS, applying the KISS principle and being
able to fine-tune some details if needed.

How-to run your mail server
===========================

*Please note that this project is still in a very early stage. Do not use for
production!*

The mail server runs as a set of Docker containers. These containers are managed
through a ``docker-compose.yml`` configuration file that requires Docker Compose
to run.

First, follow instructions at https://docs.docker.com to setup Docker and Docker
Compose properly for your system. Then download the main configuration file:

```
wget https://freeposte.io/docker-compose.yml
```

This file contains instructions about which containers to run and how they will
interact. You should also create a data directory. Freeposte will use ``/data``
as a sane default:

```
mkdir -p /data
```

Finally, you can run your mail server:

```
docker-compose up -d
```

General architecture
====================

The mail infrastructure is based on a standard MTA-LDA :

 * Postfix with an SQLite database for transport ;
 * Dovecot with an SQLite database for delivery and access ;
 * Spamassassin for spam filtering ;
 * ClamAV for malware filtering.

Additional Web UI :

 * Roundcube Webmail (can easily be replaced) ;
 * Administration UI based on Flask.
