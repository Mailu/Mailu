FROM alpine

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && echo "@community http://dl-3.alpinelinux.org/alpine/edge/community/" >> /etc/apk/repositories \
 && apk add --update \
     dovecot \
     dovecot-sqlite \
     dovecot-pigeonhole-plugin@community \
     dovecot-antispam-plugin@testing \
 && rm -rf /var/cache/apk/*

COPY dovecot-pigeonhole-plugin-extdata-1-r0.apk /
RUN apk add --allow-untrusted --force dovecot-pigeonhole-plugin-extdata-1-r0.apk

COPY conf /etc/dovecot
COPY sieve /var/lib/dovecot

COPY start.sh /start.sh

CMD ["/start.sh"]
