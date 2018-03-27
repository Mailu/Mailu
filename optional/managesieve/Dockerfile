FROM alpine:edge

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --no-cache \
     dovecot dovecot-sqlite dovecot-pigeonhole-plugin dovecot-pigeonhole-plugin-extdata \
     rspamd-client@testing python py-jinja2

RUN mkdir -p /var/lib/dovecot

COPY conf /conf
COPY start.py /start.py

CMD /start.py
