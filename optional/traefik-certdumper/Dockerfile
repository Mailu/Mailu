# syntax=docker/dockerfile-upstream:1.4.3

# cert dumper image
FROM ldez/traefik-certs-dumper

ENV TZ Etc/UTC
ENV LANG C.UTF-8

ARG VERSION
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache bash inotify-tools tzdata util-linux

COPY run.sh /

RUN echo $VERSION >/version

VOLUME ["/traefik"]
VOLUME ["/output"]

ENTRYPOINT ["/run.sh"]
