FROM alpine:edge

RUN apk add --no-cache python py-jinja2 rspamd rspamd-controller rspamd-proxy rspamd-fuzzy ca-certificates

RUN mkdir /run/rspamd

COPY conf/ /conf
COPY start.py /start.py

EXPOSE 11332/tcp 11334/tcp

VOLUME ["/var/lib/rspamd"]

CMD /start.py
