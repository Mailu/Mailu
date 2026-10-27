# syntax=docker/dockerfile-upstream:1.4.3

# dovecot image
FROM base

ARG VERSION
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache dovecot dovecot-lua dovecot-lmtpd dovecot-pigeonhole-plugin dovecot-pop3d dovecot-submissiond rspamd-client dovecot-fts-flatcurve lua-json4 \
  ; mkdir /var/lib/dovecot

COPY conf/ /conf/
COPY start.py /

RUN echo $VERSION >/version

# EXPOSE 110/tcp 143/tcp 993/tcp 4190/tcp 2525/tcp
HEALTHCHECK CMD /usr/local/bin/supervisor-healthcheck

VOLUME ["/mail"]

CMD ["/start.py"]
