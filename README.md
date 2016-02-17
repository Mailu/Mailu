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

Incoming e-mail
===============

Incoming e-mail is received by postfix, according to the workflow:
- ``smtpd`` receives the message;
- the domain is checked against the ``domains`` table;
- if the domain matches an active domain or the source address is allowed relay, continue;
- the mail is forwarded to Spamassassin, which appends some headers;
- the mail is fowarded to Dovecot using ``lmtp``;
- the local part and domain are checked against the ``users`` table;
- the user quota is checked;
- the mail is delivered to the local maildir.



TODO
====

The project is still at a very (very !) early stage.
This is more of a roadmap than a proper TODO list. Please poke me or pull
request if you would like to join the effort.

 - [x] Import vmm configuration files and get a simple postfix/dovecot running with SQLite.
 - [x] Add support for spamassassin.
 - [ ] Add support for clamav.
 - [ ] Learn from user-defined spam or ham.
 - [ ] Draft a Web administration UI.
 - [ ] Implement basic features from the free (as in beer) poste.io.
 - [ ] Start using on a couple production mail servers.
 - [ ] Implement some fancy features.
