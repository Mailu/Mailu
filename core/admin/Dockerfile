# First stage to build assets
ARG DISTRO=alpine:3.14.5
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
 && for l in ca da de:de-DE en:en-GB es:es-ES eu fr:fr-FR he hu is it:it-IT ja nb_NO:no-NB nl:nl-NL pl pt:pt-PT ru sv:sv-SE zh; do \
      cp node_modules/datatables.net-plugins/i18n/${l#*:}.json assets/${l%:*}.json; \
    done \
 && node_modules/.bin/webpack-cli --color


# Actual application
FROM $DISTRO
ARG VERSION
COPY --from=balenalib/rpi-alpine:3.14 /usr/bin/qemu-arm-static /usr/bin/qemu-arm-static

ENV TZ Etc/UTC

LABEL version=$VERSION

# python3 shared with most images
RUN set -eu \
 && apk add --no-cache python3 py3-pip py3-wheel git bash tzdata \
 && pip3 install --upgrade pip

RUN mkdir -p /app
WORKDIR /app

COPY requirements-prod.txt requirements.txt
RUN set -eu \
 && apk add --no-cache libressl curl postgresql-libs mariadb-connector-c \
 && apk add --no-cache --virtual build-dep libressl-dev libffi-dev python3-dev build-base postgresql-dev mariadb-connector-c-dev cargo \
 && pip install --upgrade pip \
 && pip install -r requirements.txt \
 && apk del --no-cache build-dep

COPY --from=assets static ./mailu/static
COPY mailu ./mailu
COPY migrations ./migrations
COPY start.py /start.py
COPY audit.py /audit.py

RUN pybabel compile -d mailu/translations

EXPOSE 80/tcp
VOLUME ["/data","/dkim"]
ENV FLASK_APP mailu

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/sso/login?next=ui.index || exit 1
RUN echo $VERSION >> /version
