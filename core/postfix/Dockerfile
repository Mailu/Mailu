<<<<<<< HEAD
# syntax=docker/dockerfile-upstream:1.4.3
=======
ARG DISTRO=alpine:3.14.5
>>>>>>> a54a7841 (Update alpine-linux to 3.14.5 - Zlib security FIX)

# postfix image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache cyrus-sasl-login postfix postfix-pcre logrotate

COPY conf/ /conf/
COPY start.py /

RUN echo $VERSION >/version

#EXPOSE 25/tcp 10025/tcp
HEALTHCHECK --start-period=30s CMD ! /usr/libexec/postfix/master -t

VOLUME ["/queue"]

CMD /start.py
