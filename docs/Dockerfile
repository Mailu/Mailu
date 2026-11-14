# Convert .rst files to .html in temporary build container
FROM python:3.14.7-alpine3.24 AS build

ARG version=master
ENV VERSION=$version

COPY requirements.txt /requirements.txt
COPY . /docs

RUN --mount=type=secret,id=github_token,required=false set -euxo pipefail \
  ; machine="$(uname -m)" \
  ; deps="gcc musl-dev graphviz" \
  ; [[ "${machine}" != x86_64 ]] && \
      deps="${deps} cargo" \
  ; apk add --no-cache --virtual .build-deps ${deps} \
  ; set +x \
  ; github_token="$(cat /run/secrets/github_token 2>/dev/null || true)" \
  ; if [[ "${machine}" == armv7* ]]; then \
      mkdir -p /root/.cargo/registry/index; \
      for attempt in 1 2 3; do \
        if [ -n "$github_token" ]; then \
          auth_header="$(printf 'x-access-token:%s' "$github_token" | base64 | tr -d '\n')"; \
          if git -c "http.extraheader=AUTHORIZATION: basic $auth_header" clone --bare https://github.com/rust-lang/crates.io-index.git /root/.cargo/registry/index/github.com-1285ae84e5963aae; then clone_status=0; else clone_status=$?; fi; \
          unset auth_header; \
        elif git clone --bare https://github.com/rust-lang/crates.io-index.git /root/.cargo/registry/index/github.com-1285ae84e5963aae; then clone_status=0; else clone_status=$?; fi; \
        if [ "$clone_status" -eq 0 ]; then break; fi; \
        rm -rf /root/.cargo/registry/index/github.com-1285ae84e5963aae; \
        if [ "$attempt" -eq 3 ]; then exit 1; fi; \
        sleep 5; \
      done; \
    fi \
  ; unset github_token \
  ; set -x \
  ; pip3 install -r /requirements.txt \
  ; mkdir -p /build/$VERSION/ \
  ; dot -Tsvg /docs/mailu-network-diagram.dot -o /docs/contributors/mailu-network-diagram.svg \
  ; sphinx-build -W /docs /build/$VERSION \
  ; apk del .build-deps \
  ; rm -rf /root/.cargo


# Build nginx deployment image including generated html
FROM nginx:1.31.6-alpine

# TODO: Remove or reconsider this upgrade once cached Python and libexpat stay
# aligned; the cached Python build can fail importing pyexpat in Supervisor.
RUN apk add --no-cache supervisor \
  && apk upgrade --no-cache python3

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

HEALTHCHECK CMD supervisorctl status nginx | grep -q RUNNING && wget -q -O /dev/null "http://127.0.0.1/${VERSION}/"

CMD ["/start.sh"]
RUN echo $pinned_version >> /version
