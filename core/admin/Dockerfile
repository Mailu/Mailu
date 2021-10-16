# First stage to build assets
ARG DISTRO=alpine:3.14.2
ARG ARCH=""

FROM ${ARCH}node:16 as assets

COPY package.json ./
RUN set -eu \
 && npm config set update-notifier false \
 && npm install --no-fund

COPY webpack.config.js ./
COPY assets ./assets
RUN set -eu \
 && sed -i 's/#007bff/#55a5d9/' node_modules/admin-lte/build/scss/_bootstrap-variables.scss \
 && for l in ca da de:de_de en:en-gb es:es_es eu fr:fr_fr he hu is it:it_it ja nb_NO:no_nb nl:nl_nl pl pt:pt_pt ru sv:sv_se zh; do \
      cp node_modules/datatables.net-plugins/i18n/${l#*:}.json assets/${l%:*}.json; \
    done \
 && node_modules/.bin/webpack-cli --color


# Actual application
FROM $DISTRO
COPY --from=balenalib/rpi-alpine:3.14 /usr/bin/qemu-arm-static /usr/bin/qemu-arm-static

# python3 shared with most images
RUN set -eu \
 && apk add --no-cache python3 py3-pip git bash \
 && pip3 install --upgrade pip

RUN mkdir -p /app
WORKDIR /app

COPY requirements-prod.txt requirements.txt
RUN set -eu \
 && apk add --no-cache libressl curl postgresql-libs mariadb-connector-c \
 && apk add --no-cache --virtual build-dep libressl-dev libffi-dev python3-dev build-base postgresql-dev mariadb-connector-c-dev cargo \
 && pip3 install -r requirements.txt \
 && apk del --no-cache build-dep

COPY --from=assets static ./mailu/ui/static
COPY mailu ./mailu
COPY migrations ./migrations
COPY start.py /start.py

RUN pybabel compile -d mailu/translations

EXPOSE 80/tcp
VOLUME ["/data","/dkim"]
ENV FLASK_APP mailu

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/ui/login?next=ui.index || exit 1
