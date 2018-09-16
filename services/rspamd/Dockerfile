FROM alpine:3.7

RUN apk add --no-cache python py-jinja2 rspamd rspamd-controller rspamd-proxy ca-certificates

RUN mkdir /run/rspamd

COPY conf/ /conf
COPY start.py /start.py

# Temporary fix to remove references to rspamd-fuzzy for now
RUN sed -i '/fuzzy/,$d' /etc/rspamd/rspamd.conf

CMD /start.py
