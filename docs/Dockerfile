# Convert .rst files to .html in temporary build container
FROM python:3.14.7-alpine3.24 AS build

ARG version=master
ENV VERSION=$version

COPY requirements.txt /requirements.txt
COPY . /docs

RUN set -euxo pipefail \
  ; machine="$(uname -m)" \
  ; deps="gcc musl-dev graphviz" \
  ; [[ "${machine}" != x86_64 ]] && \
      deps="${deps} cargo" \
  ; apk add --no-cache --virtual .build-deps ${deps} \
  ; [[ "${machine}" == armv7* ]] && \
      mkdir -p /root/.cargo/registry/index && \
      git clone --bare https://github.com/rust-lang/crates.io-index.git /root/.cargo/registry/index/github.com-1285ae84e5963aae \
  ; pip3 install -r /requirements.txt \
  ; mkdir -p /build/$VERSION/ \
  ; dot -Tsvg /docs/mailu-network-diagram.dot -o /docs/contributors/mailu-network-diagram.svg \
  ; sphinx-build -W /docs /build/$VERSION \
  ; apk del .build-deps \
  ; rm -rf /root/.cargo


# Build nginx deployment image including generated html
FROM nginx:1.31.6-alpine

RUN apk add --no-cache supervisor

ARG version=master
ARG pinned_version=master
ENV VERSION=$version
ENV TZ=Etc/UTC
LABEL version=$VERSION

COPY ./nginx.conf /etc/nginx/conf.d/default.conf
COPY ./start.sh /start.sh
COPY --from=build /build/$VERSION /build/$VERSION
RUN chmod 755 /start.sh

EXPOSE 80/tcp

HEALTHCHECK CMD supervisorctl -c /tmp/mailu-supervisorctl.conf status nginx | grep -q RUNNING && wget -q -O /dev/null "http://127.0.0.1/${VERSION}/"

CMD ["/start.sh"]
RUN echo $pinned_version >> /version
