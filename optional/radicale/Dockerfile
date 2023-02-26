# syntax=docker/dockerfile-upstream:1.4.3

# webdav image
FROM base

ARG VERSION=local
LABEL version=$VERSION

COPY radicale.conf /

RUN echo $VERSION >/version

#EXPOSE 5232/tcp
HEALTHCHECK --retries=10 --interval=2s CMD curl -m 1 -f -L http://localhost:5232/ || exit 1

VOLUME ["/data"]

CMD radicale -S -C /radicale.conf
