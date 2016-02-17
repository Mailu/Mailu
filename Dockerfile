FROM debian:jessie

RUN export DEBIAN_FRONTEND=noninteractive \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      postfix dovecot-imapd dovecot-sqlite dovecot-lmtpd \
      dovecot-sieve dovecot-managesieved \
      dovecot-antispam spamassassin spamc clamav \
      supervisor rsyslog \
 && apt-get clean

# When installed non-interactively, the file does not get copied to the
# postfix chroot, thus causing smtpd to fail.
RUN cp /etc/services /var/spool/postfix/etc/

ADD config /etc/

# Explicitely specify the configuration file to avoid problems when
# the default configuration path changes.
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
