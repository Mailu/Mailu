FROM alpine:edge

RUN apk add --no-cache \
     dovecot dovecot-pop3d dovecot-lmtpd dovecot-pigeonhole-plugin rspamd-client \
     python3 py3-pip \
 && pip3 install jinja2 podop

COPY conf /conf
COPY sieve /var/lib/dovecot
COPY start.py /start.py

EXPOSE 110/tcp 143/tcp 993/tcp 4190/tcp 2525/tcp

CMD /start.py
