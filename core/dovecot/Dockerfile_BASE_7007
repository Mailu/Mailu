FROM alpine:edge

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --no-cache \
     dovecot dovecot-sqlite dovecot-pigeonhole-plugin dovecot-pigeonhole-plugin-extdata \
     rspamd-client@testing python py-jinja2

COPY conf /conf
COPY sieve /var/lib/dovecot
COPY start.py /start.py

EXPOSE 110/tcp 143/tcp 993/tcp 4190/tcp 2525/tcp

CMD /start.py
