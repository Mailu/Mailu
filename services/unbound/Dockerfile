FROM python:3-alpine

RUN apk add --no-cache unbound curl bind-tools \
  && pip3 install jinja2 \
  && curl -o /etc/unbound/root.hints https://www.internic.net/domain/named.cache \
  && chown root:unbound /etc/unbound \
  && chmod 775 /etc/unbound \
  && apk del --no-cache curl \
  && /usr/sbin/unbound-anchor -a /etc/unbound/trusted-key.key | true

COPY start.py /start.py
COPY unbound.conf /unbound.conf

EXPOSE 53/udp 53/tcp

CMD /start.py

HEALTHCHECK CMD dig @127.0.0.1 || exit 1
