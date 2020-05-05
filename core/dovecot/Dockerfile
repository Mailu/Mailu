ARG DISTRO=debian:buster-slim
FROM $DISTRO as builder
WORKDIR /tmp
RUN echo "deb-src http://deb.debian.org/debian stable main" >> /etc/apt/sources.list
RUN apt-get update && apt-get -y build-dep dovecot-core\
  && rm -rf /var/lib/apt/lists
### Below is needed as buster provides libicu63, and fts-xapian requires >=64
RUN echo "deb-src http://deb.debian.org/debian experimental main" >> /etc/apt/sources.list\
  && apt-get update\
  && apt-get install -y --no-install-recommends build-essential fakeroot devscripts\
  && apt-get build-dep -y libicu-dev\
  && apt-get source -y libicu-dev\
  && cd icu-67.1\
  && debuild -b -uc\
  && cd .. 
RUN dpkg -i --force-all libicu67_67.1*.deb icu-devtools_67.1*.deb libicu-dev_67.1*.deb
###
RUN apt-get update && apt-get install -y dovecot-dev git libxapian-dev libicu-dev libsqlite3-dev\
  && rm -rf /var/lib/apt/lists
RUN git clone https://github.com/grosjo/fts-xapian.git \
  && cd fts-xapian \
  && git checkout 1.2.7 \
  && autoreconf -vi \
  && PANDOC=false ./configure --with-dovecot=/usr/lib/dovecot \
  && make \
  && make install

FROM $DISTRO
# python3 shared with most images
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
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends\
  dovecot-core dovecot-imapd dovecot-lmtpd dovecot-pop3d dovecot-submissiond\
  dovecot-sieve dovecot-managesieved rspamd xapian-tools netcat\
  && rm -rf /var/lib/apt/lists

### Below is needed as buster provides libicu63, and fts-xapian requires >=64
COPY --from=builder /tmp/*.deb /tmp/
RUN dpkg -i /tmp/libicu67*.deb
###

COPY --from=builder /usr/lib/dovecot/modules/lib21_fts_xapian_plugin.* /usr/lib/dovecot/modules/

COPY conf /conf
COPY start.py /start.py

EXPOSE 110/tcp 143/tcp 993/tcp 4190/tcp 2525/tcp
VOLUME ["/mail"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD echo QUIT|nc localhost 110|grep "Dovecot ready."
