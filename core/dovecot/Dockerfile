<<<<<<< HEAD
# syntax=docker/dockerfile-upstream:1.4.3
=======
ARG DISTRO=alpine:3.13
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
>>>>>>> 2b37be98 (Use alpine 3.13 to fix CVE-2020-25275 and CVE-2020-24386)

# dovecot image
FROM base

ARG VERSION
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache 'dovecot<2.4' dovecot-lmtpd dovecot-pigeonhole-plugin dovecot-pop3d dovecot-submissiond rspamd-client dovecot-fts-flatcurve \
  ; mkdir /var/lib/dovecot

COPY conf/ /conf/
COPY start.py /

RUN echo $VERSION >/version

# EXPOSE 110/tcp 143/tcp 993/tcp 4190/tcp 2525/tcp
HEALTHCHECK CMD kill -0 `cat /run/dovecot/master.pid`

VOLUME ["/mail"]

CMD /start.py
