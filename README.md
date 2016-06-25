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

General architecture
====================

The mail infrastructure is based on a standard MTA-LDA pattern :

 * Postfix for incoming and outgoing emails ;
 * Rmilter as a filtering interface before delivery (with rspamd and ClamAV) ;
 * Dovecot as a delivery agent and reading (IMAP) server ;
 * Roundcube (or any Webmail) as a user-friendly Web client ;
 * Fetchmail as a client to fetch remote accounts (POP/IMAP) ;
 * Freeposte (Flask application) as an administration interface.

![Architecture](doc/archi.png)

Running a mail server
=====================

Freeposte runs on top of Docker for easy packaging and upgrades. All you need
is a proper system with Docker and Compose installed, then simply download
the ``docker-compose.yml`` and sample ``freeposte.env``, tune them to your
needs and fire up the mail server:

```
docker-compose up -d
```

For a detailed walktrough, see ``INSTALL.md``. Also, see ``MANAGE.md`` for
details about daily maintenance of your mail server.

Development environment
=======================

The administration Web interface requires a proper dev environment that can easily be setup using ``virtualenv`` (make sure you are using Python 3) :

```
cd admin
virtualenv .
source bin/activate
pip install -r requirements.txt
```

You can then export the path to the development database:

```
export SQLALCHEMY_DATABASE_URI=sqlite:///path/to/dev.db
```

And finally run the server with debug enabled:

```
python manage.py runserver
```

Philosophy
==========

The mailserver is designed as a whole, some images are therefore not best
suited for reuse outside this project. All images should however follow
Docker best practices and be as generic as possible :

 - even if not suited for reuse, they should be simple enough to
   fit as base images for other projects,
 - interesting settings should be available as environment variables
 - base images should be well-trusted (officiel Alpine or Debian for instance).
