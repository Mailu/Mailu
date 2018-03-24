FROM alpine:edge

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --no-cache \
     dovecot dovecot-sqlite dovecot-mysql dovecot-pigeonhole-plugin dovecot-pigeonhole-plugin-extdata \
     rspamd-client@testing python py-jinja2 \
 && mkdir -p /mail

COPY conf /conf
COPY sieve /var/lib/dovecot
COPY start.py /start.py

CMD /start.py
