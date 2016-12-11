FROM alpine:edge

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --update \
     dovecot dovecot-sqlite dovecot-pigeonhole-plugin dovecot-pigeonhole-plugin-extdata \
     rspamd-client@testing \
     bash \
 && rm -rf /var/cache/apk/*

COPY conf /etc/dovecot
COPY sieve /var/lib/dovecot

COPY start.sh /start.sh

CMD ["/start.sh"]
