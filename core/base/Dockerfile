# syntax=docker/dockerfile-upstream:1.4.3

# base system image (intermediate)
# When updating this tag, first mirror it with .github/workflows/mirror.yml.
ARG DISTRO=ghcr.io/mailu/alpine:3.24.2
FROM $DISTRO AS system

ENV TZ=Etc/UTC LANG=C.UTF-8

ARG MAILU_UID=1000
ARG MAILU_GID=1000

RUN set -euxo pipefail \
  ; addgroup -Sg ${MAILU_GID} mailu \
  ; adduser -Sg ${MAILU_UID} -G mailu -h /app -g "mailu app" -s /bin/bash mailu \
  ; apk add --no-cache bash ca-certificates curl python3 tzdata \
  ; ! [[ "$(apk --print-arch)" == x86_64 ]] \
    || apk add --no-cache --repository=http://dl-cdn.alpinelinux.org/alpine/edge/testing hardened-malloc

WORKDIR /app

CMD ["/bin/bash"]


# build virtual env (intermediate)
FROM system AS build

ARG SNUFFLEUPAGUS_VERSION=0.14.0

# uv is pinned to the version packaged by alpine, so builds do not drift with
# the upstream image tag. It is only needed in this stage.
RUN set -euxo pipefail \
  ; apk add --no-cache uv=0.11.19-r0

# The workspace lock file drives the install. Only the manifests of the
# workspace members are copied, plus the libs sources that get built.
COPY pyproject.toml uv.lock ./
COPY core/admin/pyproject.toml core/admin/
COPY core/base/libs/ core/base/libs/

ENV \
  VIRTUAL_ENV=/app/venv \
  UV_PROJECT_ENVIRONMENT=/app/venv \
  UV_PYTHON_DOWNLOADS=never \
  PATH="/app/venv/bin:${PATH}" \
  CXXFLAGS="-g -O2 -fdebug-prefix-map=/app=. -fstack-protector-strong -Wformat -Werror=format-security -fstack-clash-protection -fexceptions" \
  CFLAGS="-g -O2 -fdebug-prefix-map=/app=. -fstack-protector-strong -Wformat -Werror=format-security -fstack-clash-protection -fexceptions" \
  CPPFLAGS="-Wdate-time -D_FORTIFY_SOURCE=2" \
  LDFLAGS="-Wl,-z,noexecstack -Wl,-z,relro -Wl,-z,now" \
  SNUFFLEUPAGUS_URL="https://github.com/jvoisin/snuffleupagus/archive/refs/tags/v${SNUFFLEUPAGUS_VERSION}.tar.gz"

# snuffleupagus' Makefile calls the unversioned "phpize", which alpine ships
# only for its current default php -- and that moves every release. Pin both
# wrappers to the php it builds for.
RUN set -euxo pipefail \
  ;  machine="$(apk --print-arch)" \
  ; deps="build-base gcc libffi-dev python3-dev mariadb-dev" \
  ; [[ "${machine}" != x86_64 ]] && \
      deps="${deps} rust cargo cmake git libretls-dev mariadb-connector-c-dev postgresql-dev" \
  ; apk add --virtual .build-deps ${deps} \
  ; [[ "${machine}" == armv7* ]] && \
      mkdir -p /root/.cargo/registry/index && \
      git clone --bare https://github.com/rust-lang/crates.io-index.git /root/.cargo/registry/index/github.com-1285ae84e5963aae \
  # bcrypt 4.3 builds from source on arm/v7 and uses Python's stable ABI.
  ; PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 uv sync --locked --all-packages --no-dev --no-editable --no-cache \
  ; curl -sL ${SNUFFLEUPAGUS_URL} | tar xz \
  ; cd snuffleupagus-${SNUFFLEUPAGUS_VERSION} \
  ; rm -rf src/tests/*php7*/ src/tests/*session*/ src/tests/broken_configuration/ src/tests/*cookie* src/tests/upload_validation/ \
  ; apk add --virtual .build-deps php84-dev php84-cgi php84-simplexml php84-xml pcre-dev build-base php84-pear php84-openssl re2c \
  ; ln -sf /usr/bin/phpize84 /usr/bin/phpize \
  ; ln -sf /usr/bin/php-config84 /usr/bin/php-config \
  ; pecl84 install vld-beta \
  ; make -j $(grep -c processor /proc/cpuinfo) release \
  ; cp src/.libs/snuffleupagus.so /app \
  ; rm -rf /root/.cargo /tmp/*.pem /root/.cache

# base mailu image
FROM system

COPY --from=build /app/venv/ /app/venv/
COPY --chown=root:root --from=build /app/snuffleupagus.so /usr/lib/php84/modules/

ENV \
  VIRTUAL_ENV=/app/venv \
  PATH="/app/venv/bin:${PATH}" \
  ADMIN_ADDRESS="admin" \
  FRONT_ADDRESS="front" \
  FTS_ATTACHMENTS_ADDRESS="tika" \
  SMTP_ADDRESS="smtp" \
  IMAP_ADDRESS="imap" \
  OLETOOLS_ADDRESS="oletools" \
  REDIS_ADDRESS="redis" \
  ANTIVIRUS_ADDRESS="antivirus" \
  ANTISPAM_ADDRESS="antispam" \
  WEBMAIL_ADDRESS="webmail" \
  WEBDAV_ADDRESS="webdav"
