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

General architecture
====================

The mail infrastructure is based on a standard MTA-LDA pattern :

 * Postfix for incoming and outgoing emails ;
 * Amavis as a filtering interface before delivery (with SpamaAssassin and ClamAV) ;
 * Dovecot as a delivery agent and reading (IMAP) server ;
 * Roundcube (or any Webmail) as a user-friendly Web client ;
 * Freeposte (Flask application) as an administration interface.

![Architecture](doc/archi.png)

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
wget https://raw.githubusercontent.com/kaiyou/freeposte.io/master/docker-compose.yml
```

This file contains instructions about which containers to run and how they will
interact. You should also create a data directory. Freeposte will use ``/data``
as a sane default:

```
mkdir -p /data
```

Otherwise, simply edit the ``docker-compose.yml`` to match your requirements. Finally, you can run your mail server:

```
docker-compose up -d
```

Monitoring the mail server
==========================

Logs are managed by Docker directly. You can easily read your logs using :

```
docker-compose logs
```

Docker is able to forward logs to multiple log engines. Read the following documentation or details: https://docs.docker.com/engine/admin/logging/overview/.

Building from source
====================

You can simply build all the containers from source using the ``docker-compose.yml``. First clone the Git repository:

```
git clone https://github.com/kaiyou/freeposte.io.git
```

Then build all the images :

```
docker-compose build
```

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
python run.py
```
