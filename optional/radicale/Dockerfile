<<<<<<< HEAD
# syntax=docker/dockerfile-upstream:1.4.3
=======
ARG DISTRO=alpine:3.14.5
FROM $DISTRO
ARG VERSION
>>>>>>> a54a7841 (Update alpine-linux to 3.14.5 - Zlib security FIX)

# webdav image
FROM base

ARG VERSION=local
LABEL version=$VERSION

COPY radicale.conf /

RUN echo $VERSION >/version

#EXPOSE 5232/tcp
HEALTHCHECK CMD ["/bin/sh", "-c", "ps ax | grep [/]radicale.conf"]

VOLUME ["/data"]

CMD radicale -S -C /radicale.conf
