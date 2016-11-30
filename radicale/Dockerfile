FROM alpine:edge

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --update \
     radicale@testing \
 && rm -rf /var/cache/apk/*

COPY radicale.conf /radicale.conf

CMD radicale -f -S -C /radicale.conf
