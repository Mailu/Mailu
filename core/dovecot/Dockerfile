FROM alpine:3.8

RUN apk add --no-cache \
     dovecot dovecot-pigeonhole-plugin dovecot-fts-lucene rspamd-client \
     bash python3 py3-pip \
 && pip3 install --upgrade pip \
 && pip3 install jinja2 podop tenacity

COPY conf /conf
COPY start.py /start.py

EXPOSE 110/tcp 143/tcp 993/tcp 4190/tcp 2525/tcp
VOLUME ["/data", "/mail"]

CMD /start.py
