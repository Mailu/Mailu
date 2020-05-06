ARG DISTRO=debian:buster-slim
FROM $DISTRO
# python3 shared with most images
RUN apt-get update && apt-get install -y --no-install-recommends\
  python3 curl python3-pip git python3-multidict python3-yarl\
  python3-wheel python3-setuptools\
  && rm -rf /var/lib/apt/lists \
  && pip3 install --upgrade pip

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube
RUN pip3 install socrate==0.2.0

# Image specific layers under this line
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends\
  unbound curl dnsutils\
  && curl -o /etc/unbound/root.hints https://www.internic.net/domain/named.cache\
  && chown root:unbound /etc/unbound\
  && chmod 775 /etc/unbound\
  && apt-get autoremove --purge -y curl\
  && /usr/sbin/unbound-anchor -a /etc/unbound/trusted-key.key | true\
  && rm -rf /var/lib/apt/lists

COPY start.py /start.py
COPY unbound.conf /unbound.conf

EXPOSE 53/udp 53/tcp

CMD /start.py

HEALTHCHECK CMD dig @127.0.0.1 || exit 1
