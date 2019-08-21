FROM alpine:3.10

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --no-cache radicale@testing curl bash

COPY radicale.conf /radicale.conf

EXPOSE 5232/tcp
VOLUME ["/data"]

CMD radicale -f -S -C /radicale.conf

HEALTHCHECK CMD curl -f -L http://localhost:5232/ || exit 1
