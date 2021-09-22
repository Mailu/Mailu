ARG DISTRO=alpine:3.14.2
FROM $DISTRO
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip git bash py3-multidict py3-yarl \
  && pip3 install --upgrade pip

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube
RUN pip3 install socrate==0.2.0

# Shared layer between dovecot and postfix
RUN pip3 install "podop>0.2.5"

# Image specific layers under this line
RUN apk add --no-cache --virtual .build-deps gcc musl-dev python3-dev
RUN pip3 install --no-binary :all: postfix-mta-sts-resolver==1.0.1
RUN apk del .build-deps gcc musl-dev python3-dev

RUN apk add --no-cache postfix postfix-pcre cyrus-sasl-login

COPY conf /conf
COPY start.py /start.py

EXPOSE 25/tcp 10025/tcp
VOLUME ["/queue"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD echo QUIT|nc localhost 25|grep "220 .* ESMTP Postfix"
