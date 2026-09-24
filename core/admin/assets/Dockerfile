# syntax=docker/dockerfile-upstream:1.4.3

# The output is static, so arm/v7 can use Node on the builder's supported platform.
FROM --platform=$BUILDPLATFORM node:26.10.0-alpine3.24

WORKDIR /work

COPY package.json ./

RUN set -euxo pipefail \
  ; npm config set update-notifier false \
  ; echo "#!/bin/sh" >/usr/local/bin/husky \
  ; chmod +x /usr/local/bin/husky \
  ; npm install --no-audit --no-fund

COPY assets/ ./assets/
COPY webpack.config.js ./

RUN set -euxo pipefail \
  ; node_modules/.bin/webpack-cli --color
