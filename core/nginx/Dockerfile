# syntax=docker/dockerfile-upstream:1.4.3

ARG MAILU_BASE=base

# build static assets (intermediate)
FROM ${MAILU_BASE} as static

COPY static/ /static/

RUN set -euxo pipefail \
  ; gzip -k9 /static/*.ico /static/*.txt \
  ; chmod a+rX-w -R /static


# nginx image
FROM ${MAILU_BASE}

ARG VERSION
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache certbot 'nginx>=1.28.3-r8' nginx-mod-http-brotli 'nginx-mod-mail>=1.28.3-r8' openssl \
  ; apk add --no-cache --repository=https://dl-cdn.alpinelinux.org/alpine/v3.21/main 'dovecot<2.4' 'dovecot-lua<2.4' 'dovecot-pigeonhole-plugin<2.4' 'dovecot-lmtpd<2.4' 'dovecot-pop3d<2.4' 'dovecot-submissiond<2.4'

COPY conf/ /conf/
COPY --from=static /static/ /static/
COPY *.py /
COPY dovecot/proxy.conf dovecot/login.lua /dovecot_conf/

RUN echo $VERSION >/version

EXPOSE 80/tcp 443/tcp 110/tcp 143/tcp 465/tcp 587/tcp 993/tcp 995/tcp 25/tcp 4190/tcp
# EXPOSE 10025/tcp 10143/tcp 14190/tcp
HEALTHCHECK --start-period=60s CMD curl -m3 -skfLo /dev/null http://127.0.0.1:10204/health && kill -0 `cat /run/dovecot/master.pid`

VOLUME ["/certs", "/overrides"]

CMD /start.py
