FROM alpine:edge

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --update \
     rspamd@testing rsyslog \
 && rm -rf /var/cache/apk/*
 
RUN mkdir /run/rspamd

CMD ["rspamd", "-f", "-i"]