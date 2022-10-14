# syntax=docker/dockerfile-upstream:1.4.3

# base system image (intermediate)
ARG DISTRO=alpine:3.14.5
FROM $DISTRO as system

ENV TZ=Etc/UTC LANG=C.UTF-8

ARG MAILU_UID=1000
ARG MAILU_GID=1000

RUN set -euxo pipefail \
  ; addgroup -Sg ${MAILU_GID} mailu \
  ; adduser -Sg ${MAILU_UID} -G mailu -h /app -g "mailu app" -s /bin/bash mailu \
  ; apk add --no-cache bash ca-certificates python3 tzdata

WORKDIR /app

CMD /bin/bash


# build virtual env (intermediate)
FROM system as build

ENV VIRTUAL_ENV=/app/venv

COPY requirements-*.txt ./

RUN set -euxo pipefail \
  ; apk add --no-cache py3-pip \
  ; python3 -m venv ${VIRTUAL_ENV} \
  ; ${VIRTUAL_ENV}/bin/pip install --no-cache-dir -r requirements-build.txt

ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY libs/ libs/

RUN set -euxo pipefail \
  ; pip install --no-cache-dir -r requirements-prod.txt \
 || ( \
      apk add --no-cache --virtual .build-deps \
          build-base cargo gcc libffi-dev libressl-dev mariadb-connector-c-dev \
          musl-dev postgresql-dev python3-dev \
    ; pip install --no-cache-dir -r requirements-prod.txt \
    ; apk del .build-deps \
  )


# base mailu image
FROM system

COPY --from=build /app/venv/ /app/venv/

ENV VIRTUAL_ENV=/app/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
