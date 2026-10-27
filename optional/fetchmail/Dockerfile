# syntax=docker/dockerfile-upstream:1.4.3

# fetchmail image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache fetchmail openssl \
  ; mkdir -p /data

COPY fetchmail.py /
COPY start.py /

RUN echo $VERSION >/version

HEALTHCHECK --start-period=350s CMD /usr/local/bin/supervisor-healthcheck

CMD ["/start.py"]
