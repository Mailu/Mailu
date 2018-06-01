FROM alpine:edge

RUN apk add --no-cache python py-jinja2 rspamd rspamd-controller rspamd-proxy ca-certificates

RUN mkdir /run/rspamd

COPY conf/ /conf
COPY start.py /start.py

# Temporary fix to remove references to rspamd-fuzzy for now
RUN sed -i '/fuzzy/,$d' /etc/rspamd/rspamd.conf

EXPOSE 11332/tcp 11334/tcp

CMD /start.py
