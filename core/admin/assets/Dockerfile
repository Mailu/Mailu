# syntax=docker/dockerfile-upstream:1.4.3

FROM node:21-alpine3.18

WORKDIR /work

COPY package.json ./

RUN set -euxo pipefail \
  ; npm config set update-notifier false \
  ; npm install --no-audit --no-fund \
  ; sed -i 's/#007bff/#55a5d9/' node_modules/admin-lte/build/scss/_bootstrap-variables.scss \
  ; mkdir assets \
  ; for l in ca da de:de-DE en:en-GB es:es-ES eu fa fr:fr-FR he hu is it:it-IT ja nb_NO:no-NB nl:nl-NL pl pt:pt-PT ru sv:sv-SE uk zh zh_TW:zh-HANT; do \
      cp node_modules/datatables.net-plugins/i18n/${l#*:}.json assets/${l%:*}.json; \
    done

COPY assets/ ./assets/
COPY webpack.config.js ./

RUN set -euxo pipefail \
  ; node_modules/.bin/webpack-cli --color
