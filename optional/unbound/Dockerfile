<<<<<<< HEAD
# syntax=docker/dockerfile-upstream:1.4.3
=======
ARG DISTRO=alpine:3.10
FROM $DISTRO
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip git bash py3-multidict \
  && pip3 install --upgrade pip
>>>>>>> 09ee3ce9 (Install py3-multidict from repository before installing socrate to avoid the need of gcc during build)

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
