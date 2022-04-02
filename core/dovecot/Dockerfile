ARG DISTRO=alpine:3.14.5

FROM $DISTRO
ARG VERSION
ENV TZ Etc/UTC

LABEL version=$VERSION

# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip git bash py3-multidict py3-yarl tzdata \
  && pip3 install --upgrade pip

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube
RUN pip3 install socrate==0.2.0

# Shared layer between dovecot and postfix
RUN pip3 install "podop>0.2.5"

# Image specific layers under this line
RUN apk add --no-cache \
  dovecot dovecot-lmtpd dovecot-pop3d dovecot-submissiond dovecot-pigeonhole-plugin rspamd-client xapian-core dovecot-fts-xapian \
  && mkdir /var/lib/dovecot

COPY conf /conf
COPY start.py /start.py

EXPOSE 110/tcp 143/tcp 993/tcp 4190/tcp 2525/tcp
VOLUME ["/mail"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD echo QUIT|nc localhost 110|grep "Dovecot ready."
RUN echo $VERSION >> /version