<<<<<<< HEAD
# syntax=docker/dockerfile-upstream:1.4.3
=======
ARG DISTRO=alpine:3.14.5
FROM $DISTRO
ARG VERSION
>>>>>>> a54a7841 (Update alpine-linux to 3.14.5 - Zlib security FIX)

# resolver image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache bind-tools unbound \
  ; curl -so /etc/unbound/root.hints https://www.internic.net/domain/named.cache \
  ; chown root:unbound /etc/unbound \
  ; chmod 775 /etc/unbound \
  ; /usr/sbin/unbound-anchor -a /etc/unbound/trusted-key.key || true

COPY unbound.conf /
COPY start.py /

RUN echo $VERSION >/version

#EXPOSE 53/udp 53/tcp
HEALTHCHECK CMD dig @127.0.0.1 || exit 1

CMD /start.py
