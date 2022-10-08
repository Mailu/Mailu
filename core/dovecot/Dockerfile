# syntax=docker/dockerfile-upstream:1.4.3

# dovecot image
FROM base

ARG VERSION
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache dovecot dovecot-fts-xapian dovecot-lmtpd dovecot-pigeonhole-plugin dovecot-pop3d dovecot-submissiond rspamd-client xapian-core \
  ; mkdir /var/lib/dovecot

COPY conf/ /conf/
COPY start.py /

RUN echo $VERSION >/version

EXPOSE 110/tcp 143/tcp 993/tcp 4190/tcp 2525/tcp
HEALTHCHECK --start-period=350s CMD echo QUIT|nc localhost 110|grep "Dovecot ready."

VOLUME ["/mail"]

CMD /start.py
