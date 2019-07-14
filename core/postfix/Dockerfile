FROM alpine:3.10
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip git bash \
  && pip3 install --upgrade pip
# Shared layer between rspamd, postfix, dovecot, unbound, rainloop, roundcube and nginx
RUN pip3 install git+https://github.com/Mailu/MailuStart.git#egg=mailustart
# Shared layer between dovecot and postfix
RUN pip3 install "podop>0.2.5"
# Image specific layers under this line

RUN apk add --no-cache postfix postfix-pcre cyrus-sasl-plain

COPY conf /conf
COPY start.py /start.py

EXPOSE 25/tcp 10025/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD echo QUIT|nc localhost 25|grep "220 .* ESMTP Postfix"
