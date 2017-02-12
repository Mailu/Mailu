FROM alpine:edge

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --no-cache \
     dovecot dovecot-sqlite dovecot-pigeonhole-plugin dovecot-pigeonhole-plugin-extdata \
     rspamd-client@testing \
     bash

COPY conf /etc/dovecot
COPY sieve /var/lib/dovecot

COPY start.sh /start.sh

CMD ["/start.sh"]
