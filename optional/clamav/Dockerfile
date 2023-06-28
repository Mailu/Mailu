# syntax=docker/dockerfile-upstream:1.4.3

# clamav image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache clamav clamav-libunrar rsyslog wget

COPY conf/ /etc/clamav/
COPY start.py /

RUN echo $VERSION >/version

#EXPOSE 3310/tcp
HEALTHCHECK CMD kill -0 `cat /run/clamd.pid` && kill -0 `cat /run/freshclam.pid`

VOLUME ["/data"]

CMD /start.py
