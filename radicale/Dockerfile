FROM alpine:edge

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --no-cache radicale@testing py-dulwich@testing

COPY radicale.conf /radicale.conf

CMD radicale -f -S -C /radicale.conf
