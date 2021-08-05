ARG DISTRO=alpine:3.14
FROM $DISTRO as builder
WORKDIR /tmp
RUN apk add git build-base automake autoconf libtool dovecot-dev xapian-core-dev icu-dev
RUN git clone https://github.com/grosjo/fts-xapian.git \
  && cd fts-xapian \
  && git checkout 1.2.7 \
  && autoreconf -vi \
  && PANDOC=false ./configure --with-dovecot=/usr/lib/dovecot \
  && make \
  && make install

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
RUN apk add --no-cache \
  dovecot dovecot-lmtpd dovecot-pop3d dovecot-submissiond dovecot-pigeonhole-plugin rspamd-client xapian-core \
  && mkdir /var/lib/dovecot

COPY --from=builder /usr/lib/dovecot/lib21_fts_xapian_plugin.* /usr/lib/dovecot/

COPY conf /conf
COPY start.py /start.py

EXPOSE 110/tcp 143/tcp 993/tcp 4190/tcp 2525/tcp
VOLUME ["/mail"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD echo QUIT|nc localhost 110|grep "Dovecot ready."
