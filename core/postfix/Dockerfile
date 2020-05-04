ARG DISTRO=debian:buster-slim
FROM $DISTRO
# python3 shared with most images
#RUN apk add --no-cache \
#    python3 py3-pip git bash py3-multidict py3-yarl \
#  && pip3 install --upgrade pip
RUN apt-get update && apt-get install -y --no-install-recommends\
  python3 curl python3-pip git python3-multidict python3-yarl\
  python3-wheel python3-setuptools\
  && rm -rf /var/lib/apt/lists \
  && pip3 install --upgrade pip

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube
RUN pip3 install socrate==0.2.0

# Shared layer between dovecot and postfix
RUN pip3 install "podop>0.2.5"

# Image specific layers under this line
#RUN apk add --no-cache postfix postfix-pcre cyrus-sasl-plain
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends\
  postfix postfix-pcre sasl2-bin libsasl2-modules\
  && rm -rf /var/lib/apt/lists  

COPY conf /conf
COPY start.py /start.py

EXPOSE 25/tcp 10025/tcp
VOLUME ["/queue"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD echo QUIT|nc localhost 25|grep "220 .* ESMTP Postfix"
