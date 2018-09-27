FROM alpine:3.8

RUN apk add --no-cache \
     dovecot dovecot-pigeonhole-plugin dovecot-fts-lucene rspamd-client \
     python3 py3-pip \
 && pip3 install jinja2 podop

COPY conf /conf
COPY start.py /start.py

EXPOSE 110/tcp 143/tcp 993/tcp 4190/tcp 2525/tcp

CMD /start.py
