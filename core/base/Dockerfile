# syntax=docker/dockerfile-upstream:1.4.3

ARG DISTRO=alpine:3.14.5
FROM $DISTRO

ENV TZ Etc/UTC
ENV LANG C.UTF-8

# TODO: use intermediate image to build virtual env

RUN set -euxo pipefail \
 && adduser -s /bin/bash -Dh /app -k /var/empty -u 1000 -g mailu app \
 && apk add --no-cache bash ca-certificates tzdata python3 py3-pip py3-wheel \
 && pip3 install --no-cache-dir --upgrade pip

WORKDIR /app

COPY libs libs/

# TODO: work in virtual env (see above)
# && python3 -m venv . \
RUN set -euxo pipefail \
 && pip3 install --no-cache-dir -r libs/requirements.txt --only-binary=:all: \
 || ( apk add --no-cache --virtual .build-deps gcc musl-dev python3-dev \
      && pip3 install --no-cache-dir -r libs/requirements.txt \
      && apk del --no-cache .build-deps )

# TODO: clean image (or use intermediate - see above)
# && bin/pip uninstall -y pip distribute setuptools wheel \
# && rm -rf /tmp/* /root/.cache/pip
