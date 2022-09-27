# syntax=docker/dockerfile-upstream:1.4.3

FROM base

ARG VERSION
LABEL version=$VERSION

RUN set -euxo pipefail \
 && apk add --no-cache dovecot dovecot-lmtpd dovecot-pop3d dovecot-submissiond dovecot-pigeonhole-plugin rspamd-client xapian-core dovecot-fts-xapian \
 && mkdir /var/lib/dovecot

COPY conf /conf
COPY start.py /start.py

RUN echo $VERSION >> /version

EXPOSE 110/tcp 143/tcp 993/tcp 4190/tcp 2525/tcp
HEALTHCHECK --start-period=350s CMD echo QUIT|nc localhost 110|grep "Dovecot ready."

VOLUME ["/mail"]

CMD /start.py
