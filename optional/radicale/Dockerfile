FROM alpine:edge

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --no-cache radicale@testing py-dulwich@testing

COPY radicale.conf /radicale.conf

EXPOSE 5232/tcp

CMD radicale -f -S -C /radicale.conf
