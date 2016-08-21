Freeposte.io
============

Simple yet full-featured mail server as a set of Docker images.
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

Features
========

Main features include:

- **Standard email server**, IMAP and IMAP+, SMTP and Submission
- **Web access**, Roundcube-based Webmail and adminitration interface
- **User features**, aliases, auto-reply, auto-forward, fetched accounts
- **Admin features**, global admins, per-domain delegation, quotas
- **Security**, enforced TLS, outgoing DKIM, anti-virus scanner
- **Antispam**, auto-learn, greylisting, DMARC and SPF
- **Freedom**, all FOSS components, no tracker included

![Creating a new user](http://freeposte.io/screenshots/create.png)

Running a mail server
=====================

Freeposte.io runs on top of Docker for easy packaging and upgrades. All you need
is a proper system with Docker and Compose installed, then simply download
the ``docker-compose.yml`` and sample ``.env``, tune them to your needs and
fire up the mail server:

```
docker-compose up -d
```

For a detailed walktrough, see the [Setup Guide](https://github.com/kaiyou/freeposte.io/wiki/Setup-Guide).

Contributing
============

Freeposte.io is free software, open to suggestions and contributions. All
components are free software and compatible with the MIT license. All
specific configuration files, Dockerfiles and code are placed under the
MIT license.

For details, see the [Contributor Guide](https://github.com/kaiyou/freeposte.io/wiki/Contributors-Guide).
