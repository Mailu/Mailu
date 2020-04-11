ARG DISTRO=alpine:3.12
FROM $DISTRO
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip git bash py3-multidict \
  && pip3 install --upgrade pip

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube
RUN pip3 install socrate==0.2.0

# Image specific layers under this line
RUN echo "@testing http://dl-cdn.alpinelinux.org/alpine/edge/main" >> /etc/apk/repositories
RUN echo "@testing http://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories
RUN apk add --no-cache rspamd@testing rspamd-controller@testing rspamd-proxy@testing rspamd-fuzzy@testing ca-certificates curl

RUN mkdir /run/rspamd

COPY conf/ /conf
COPY start.py /start.py

EXPOSE 11332/tcp 11334/tcp 11335/tcp

VOLUME ["/var/lib/rspamd"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD curl -f -L http://localhost:11334/ || exit 1
