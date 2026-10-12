# Convert .rst files to .html in temporary build container
FROM python:3.14.7-alpine3.24 AS build

ARG version=master
ENV VERSION=$version \
  VIRTUAL_ENV=/venv \
  UV_PROJECT_ENVIRONMENT=/venv \
  UV_PYTHON_DOWNLOADS=never \
  PATH="/venv/bin:${PATH}"

# The docs dependencies come from the workspace lock file, so the build context is the
# repository root. Only the manifests of the workspace members are copied for resolution.
WORKDIR /lock
COPY pyproject.toml uv.lock ./
COPY core/admin/pyproject.toml core/admin/
COPY core/base/libs/ core/base/libs/
COPY docs /docs

RUN set -euxo pipefail \
  ; machine="$(uname -m)" \
  ; deps="gcc musl-dev graphviz" \
  ; [[ "${machine}" != x86_64 ]] && \
      deps="${deps} cargo" \
  ; apk add --no-cache --virtual .build-deps ${deps} \
  ; [[ "${machine}" == armv7* ]] && \
      mkdir -p /root/.cargo/registry/index && \
      git clone --bare https://github.com/rust-lang/crates.io-index.git /root/.cargo/registry/index/github.com-1285ae84e5963aae \
  ; apk add --no-cache --repository=http://dl-cdn.alpinelinux.org/alpine/v3.24/community uv=0.11.19-r0 \
  ; uv sync --locked --only-group docs --no-cache \
  ; mkdir -p /build/$VERSION/ \
  ; dot -Tsvg /docs/mailu-network-diagram.dot -o /docs/contributors/mailu-network-diagram.svg \
  ; sphinx-build -W /docs /build/$VERSION \
  ; apk del .build-deps \
  ; rm -rf /root/.cargo


# Build nginx deployment image including generated html
FROM nginx:1.31.6-alpine

ARG version=master
ARG pinned_version=master
ENV VERSION=$version
ENV TZ=Etc/UTC
LABEL version=$VERSION

COPY docs/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/$VERSION /build/$VERSION

EXPOSE 80/tcp

CMD ["nginx", "-g", "daemon off;"]
RUN echo $pinned_version >> /version
