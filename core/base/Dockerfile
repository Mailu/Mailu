# syntax=docker/dockerfile-upstream:1.4.3

# base system image (intermediate)
ARG DISTRO=alpine:3.14.5
FROM $DISTRO as system

ENV TZ Etc/UTC
ENV LANG C.UTF-8

RUN set -euxo pipefail \
  ; adduser -s /bin/bash -Dh /app -k /var/empty -u 1000 -g mailu app \
  ; apk add --no-cache bash ca-certificates python3 tzdata

WORKDIR /app

CMD /bin/bash


# build virtual env (intermediate)
FROM system as build

ENV VIRTUAL_ENV=/app/venv

RUN set -euxo pipefail \
  ; apk add --no-cache py3-pip \
  ; python3 -m venv ${VIRTUAL_ENV} \
  ; venv/bin/pip install --no-cache-dir --upgrade --no-warn-script-location pip wheel

ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY libs/ libs/
COPY --from=core ./ core/
COPY --from=optional ./ optional/

RUN set -euxo pipefail \
  ; grep -hEv '(podop|socrate)==' core/*/requirements.txt optional/*/requirements.txt \
    | sort -u >libs/requirements.txt \
\
  ; venv/bin/pip install --no-cache-dir -r libs/requirements.txt \
 || ( \
      apk add --no-cache --virtual .build-deps \
        build-base cargo gcc libffi-dev libressl-dev mariadb-connector-c-dev \
        musl-dev postgresql-dev python3-dev \
       ; venv/bin/pip install --no-cache-dir -r libs/requirements.txt \
       ; apk del .build-deps \
  ) \
\
  ; venv/bin/pip freeze > venv/requirements.txt


# base mailu image
FROM system

COPY --from=build /app/venv/ /app/venv/

ENV VIRTUAL_ENV=/app/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
