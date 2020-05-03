ARG DISTRO=debian:stable-slim
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
  rspamd ca-certificates curl\
  && rm -rf /var/lib/apt/lists

COPY conf/ /conf
COPY start.py /start.py

EXPOSE 11332/tcp 11334/tcp 11335/tcp

VOLUME ["/var/lib/rspamd"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD curl -f -L http://localhost:11334/ || exit 1
