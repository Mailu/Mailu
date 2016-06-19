FROM alpine:edge

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --update \
     rspamd@testing \
 && rm -rf /var/cache/apk/*

RUN mkdir /run/rspamd

COPY conf/ /etc/rspamd
COPY start.sh /start.sh

CMD ["/start.sh"]
