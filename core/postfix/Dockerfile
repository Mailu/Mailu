# syntax=docker/dockerfile-upstream:1.4.3

# postfix image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache cyrus-sasl-login postfix postfix-pcre logrotate

COPY conf/ /conf/
COPY start.py /
COPY chroot.py /
COPY mta_sts.py /

RUN echo $VERSION >/version

#EXPOSE 25/tcp 10025/tcp
HEALTHCHECK --start-period=30s CMD /usr/local/bin/supervisor-healthcheck

VOLUME ["/queue"]

CMD ["/start.py"]
