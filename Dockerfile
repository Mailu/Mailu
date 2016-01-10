FROM debian:jessie

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      postfix dovecot-imapd dovecot-sqlite \ # basics
      dovecot-sieve dovecot-managesieved \ # filters
      dovecot-antispam spamassassin clamav \ # additional utilities
      supervisord \ # glue
 && apt-get clean

ADD config /etc/
