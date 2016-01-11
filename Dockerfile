FROM debian:jessie

RUN export DEBIAN_FRONTEND=noninteractive \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      postfix dovecot-imapd dovecot-sqlite \
      dovecot-sieve dovecot-managesieved \
      dovecot-antispam spamassassin clamav \
      supervisor \
 && apt-get clean

ADD config /etc/

CMD ["/usr/bin/supervisord"]
