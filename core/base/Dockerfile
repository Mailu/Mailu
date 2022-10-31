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

ARG MAILU_ENV=prod

ENV VIRTUAL_ENV=/app/venv

COPY requirements-build.txt ./

RUN set -euxo pipefail \
  ; apk add --no-cache py3-pip \
  ; python3 -m venv ${VIRTUAL_ENV} \
  ; ${VIRTUAL_ENV}/bin/pip install --no-cache-dir -r requirements-build.txt \
  ; apk del -r py3-pip \
  ; rm -f /tmp/*.pem

ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY requirements-${MAILU_ENV}.txt ./
COPY libs/ libs/

RUN set -euxo pipefail \
  ; machine="$(uname -m)"; deps="" \
  ; [[ "${machine}" == arm* || "${machine}" == aarch64 ]] && deps="${deps} build-base gcc libffi-dev python3-dev" \
  ; [[ "${machine}" == armv7* ]] && deps="${deps} cargo git libressl-dev mariadb-connector-c-dev postgresql-dev" \
  ; [[ "${deps}" ]] && apk add --virtual .build-deps ${deps} \
  ; [[ "${machine}" == armv7* ]] && mkdir -p /root/.cargo/registry/index && git clone --bare https://github.com/rust-lang/crates.io-index.git /root/.cargo/registry/index/github.com-1285ae84e5963aae \
  ; pip install -r requirements-${MAILU_ENV}.txt \
  ; apk -e info -q .build-deps && apk del -r .build-deps \
  ; rm -rf /root/.cargo /root/.cache /tmp/*.pem


# base mailu image
FROM system

COPY --from=build /app/venv/ /app/venv/

ENV VIRTUAL_ENV=/app/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
