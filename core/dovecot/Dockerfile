FROM alpine:3.8
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip git bash \
  && pip3 install --upgrade pip
# Shared layer between rspamd, postfix, dovecot, unbound and nginx
RUN pip3 install git+https://github.com/usrpro/MailuStart.git#egg=mailustart
# Image specific layers under this line
RUN apk add --no-cache \
  dovecot dovecot-pigeonhole-plugin rspamd-client bash \
  && pip3 install podop \
  && mkdir /var/lib/dovecot

COPY conf /conf
COPY start.py /start.py

EXPOSE 110/tcp 143/tcp 993/tcp 4190/tcp 2525/tcp
VOLUME ["/data", "/mail"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD echo QUIT|nc localhost 110|grep "Dovecot ready."
