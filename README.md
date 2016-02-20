Freeposte.io
============

Simple yet functional and full-featured mail server as a single Docker image.
The idea behing Freeposte.io is identical to motivations that led to poste.io:
even though it looks like a Docker anti-pattern, single upgradable image
running a full-featured mail server is a truly amazing advantage for hosting
mails on modern cloud services or home-brewed Docker servers.

People from poste.io did an amazing job at accomplishing this ; any company
looking for a serious yet simple mail server with professional support should
turn to them.

This project is meant for free software supporters and hackers to reach the
same level of functionality and still be able to host a complete mail server
at little cost while running only FOSS, applying the KISS principle and being
able to fine-tune some details if needed.

How-to run your mail server
===========================

*Please note that this image is still in a very early stage. Do not use for
production!*

The mail server runs as a single Docker container. A volume should be mounted to ``/data`` for persistent storage. Simply setup Docker on your
server then run a container with the ``kaiyou/freeposte.io`` image:

```
docker run --name=freeposte -d \
 -e POSTMASTER_ADDRESS=admin@your.tld \
 -e MAIL_HOSTNAME=mail.your.tld \
 -e SECRET_KEY=yourflasksecretkey \
 -p 25:25 \
 -p 143:143 \
 -p 587:587 \
 -p 80:80 \
 -v /path/to/your/data:/data \
 kaiyou/freeposte.io
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

All components are monitored by supervisord.
