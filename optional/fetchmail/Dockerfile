<<<<<<< HEAD
# syntax=docker/dockerfile-upstream:1.4.3
=======
ARG DISTRO=alpine:3.14.5
FROM $DISTRO
ARG VERSION
>>>>>>> a54a7841 (Update alpine-linux to 3.14.5 - Zlib security FIX)

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

CMD ["/fetchmail.py"]
