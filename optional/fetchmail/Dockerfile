# syntax=docker/dockerfile-upstream:1.4.3

# fetchmail image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache fetchmail openssl \
  ; mkdir -p /data

COPY fetchmail.py /

RUN echo $VERSION >/version

HEALTHCHECK --start-period=350s CMD ["/bin/sh", "-c", "ps ax | grep [/]fetchmail.py"]

VOLUME ["/var/lib/rspamd"]

CMD ["/fetchmail.py"]
