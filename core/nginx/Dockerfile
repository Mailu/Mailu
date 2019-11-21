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

# build static assets (intermediate)
FROM base as static

COPY static/ /static/

RUN set -euxo pipefail \
  ; gzip -k9 /static/*.ico /static/*.txt \
  ; chmod a+rX-w -R /static


# nginx image
FROM base

ARG VERSION
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache certbot nginx nginx-mod-http-brotli nginx-mod-mail openssl \
  ; apk add --no-cache --repository=http://dl-cdn.alpinelinux.org/alpine/edge/main dovecot-lua dovecot-pigeonhole-plugin 'dovecot-lmtpd<2.4' dovecot-pop3d dovecot-submissiond

COPY conf/ /conf/
COPY --from=static /static/ /static/
COPY *.py /
COPY dovecot/proxy.conf dovecot/login.lua /dovecot_conf/

RUN echo $VERSION >/version

EXPOSE 80/tcp 443/tcp 110/tcp 143/tcp 465/tcp 587/tcp 993/tcp 995/tcp 25/tcp 4190/tcp
# EXPOSE 10025/tcp 10143/tcp 14190/tcp
HEALTHCHECK --start-period=60s CMD curl -skfLo /dev/null http://127.0.0.1:10204/health && kill -0 `cat /run/dovecot/master.pid`

VOLUME ["/certs", "/overrides"]

CMD /start.py
