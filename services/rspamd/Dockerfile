FROM alpine:3.8

RUN apk add --no-cache python py-jinja2 rspamd rspamd-controller rspamd-proxy rspamd-fuzzy ca-certificates py-pip curl\
 && pip install --upgrade pip \
 && pip install tenacity

RUN mkdir /run/rspamd

COPY conf/ /conf
COPY start.py /start.py

EXPOSE 11332/tcp 11334/tcp 11335/tcp

VOLUME ["/var/lib/rspamd"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD curl -f -L http://localhost:11334/ || exit 1
