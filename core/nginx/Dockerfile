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
  certbot nginx libnginx-mod-mail openssl curl\
  && rm -rf /var/lib/apt/lists\
  && pip3 install watchdog

COPY conf /conf
COPY static /static
COPY *.py /

EXPOSE 80/tcp 443/tcp 110/tcp 143/tcp 465/tcp 587/tcp 993/tcp 995/tcp 25/tcp 10025/tcp 10143/tcp
VOLUME ["/certs"]
VOLUME ["/overrides"]

CMD /start.py

HEALTHCHECK CMD curl -k -f -L http://localhost/health || exit 1
