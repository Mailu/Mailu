FROM alpine:edge

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --update \
     rmilter@testing rsyslog \
 && rm -rf /var/cache/apk/*
 
COPY rmilter.conf /etc/rmilter.conf
COPY rsyslog.conf /etc/rsyslog.conf

COPY start.sh /start.sh

CMD ["/start.sh"]