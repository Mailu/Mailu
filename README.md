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
