# syntax=docker/dockerfile-upstream:1.4.3

# dovecot image
FROM base

ARG VERSION
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache --repository=http://dl-cdn.alpinelinux.org/alpine/edge/main 'dovecot<2.4' dovecot-fts-xapian dovecot-lmtpd dovecot-pigeonhole-plugin dovecot-pop3d dovecot-submissiond xapian-core \
  ; apk add rspamd-client \
  ; mkdir /var/lib/dovecot

COPY conf/ /conf/
COPY start.py /

RUN echo $VERSION >/version

# EXPOSE 110/tcp 143/tcp 993/tcp 4190/tcp 2525/tcp
HEALTHCHECK CMD kill -0 `cat /run/dovecot/master.pid`

VOLUME ["/mail"]

CMD /start.py
