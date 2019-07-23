FROM alpine:3.10
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip git bash \
  && pip3 install --upgrade pip
# Shared layer between rspamd, postfix, dovecot, unbound, rainloop, roundcube and nginx
RUN pip3 install git+https://github.com/Mailu/MailuStart.git#egg=mailustart
# Image specific layers under this line
RUN apk add --no-cache rspamd rspamd-controller rspamd-proxy rspamd-fuzzy ca-certificates curl

RUN mkdir /run/rspamd

COPY conf/ /conf
COPY start.py /start.py

EXPOSE 11332/tcp 11334/tcp 11335/tcp

VOLUME ["/var/lib/rspamd"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD curl -f -L http://localhost:11334/ || exit 1
