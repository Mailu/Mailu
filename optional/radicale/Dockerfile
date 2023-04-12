# syntax=docker/dockerfile-upstream:1.4.3

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
