# syntax=docker/dockerfile-upstream:1.4.3

# base system image (intermediate)
ARG DISTRO=alpine:3.16.2
FROM $DISTRO as system

ENV TZ=Etc/UTC LANG=C.UTF-8

ARG MAILU_UID=1000
ARG MAILU_GID=1000

RUN set -euxo pipefail \
  ; addgroup -Sg ${MAILU_GID} mailu \
  ; adduser -Sg ${MAILU_UID} -G mailu -h /app -g "mailu app" -s /bin/bash mailu \
  ; apk add --no-cache bash ca-certificates curl python3 tzdata

WORKDIR /app

CMD /bin/bash


# build virtual env (intermediate)
FROM system as build

ARG MAILU_DEPS=prod

ENV VIRTUAL_ENV=/app/venv

COPY requirements-build.txt ./

RUN set -euxo pipefail \
  ; apk add --no-cache py3-pip \
  ; python3 -m venv ${VIRTUAL_ENV} \
  ; ${VIRTUAL_ENV}/bin/pip install --no-cache-dir -r requirements-build.txt \
  ; apk del -r py3-pip \
  ; rm -f /tmp/*.pem

ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY requirements-${MAILU_DEPS}.txt ./
COPY libs/ libs/

RUN set -euxo pipefail \
  ; pip install -r requirements-${MAILU_DEPS}.txt || \
    { \
      machine="$(uname -m)" \
    ; deps="build-base gcc libffi-dev python3-dev" \
    ; [[ "${machine}" != x86_64 ]] && \
        deps="${deps} cargo git libressl-dev mariadb-connector-c-dev postgresql-dev" \
    ; apk add --virtual .build-deps ${deps} \
    ; [[ "${machine}" == armv7 ]] && \
        mkdir -p /root/.cargo/registry/index && \
        git clone --bare https://github.com/rust-lang/crates.io-index.git /root/.cargo/registry/index/github.com-1285ae84e5963aae \
    ; pip install -r requirements-${MAILU_DEPS}.txt \
    ; apk del -r .build-deps \
    ; rm -rf /root/.cargo /tmp/*.pem \
  ; } \
  ; rm -rf /root/.cache


# base mailu image
FROM system

COPY --from=build /app/venv/ /app/venv/

ENV VIRTUAL_ENV=/app/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
