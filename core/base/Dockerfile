# syntax=docker/dockerfile-upstream:1.4.3

# base system image (intermediate)
# When updating this tag, first mirror it with .github/workflows/mirror.yml.
ARG DISTRO=ghcr.io/mailu/alpine:3.24.3
FROM $DISTRO AS system

ENV TZ=Etc/UTC LANG=C.UTF-8

ARG MAILU_UID=1000
ARG MAILU_GID=1000

RUN set -euxo pipefail \
  ; addgroup -Sg ${MAILU_GID} mailu \
  ; adduser -Sg ${MAILU_UID} -G mailu -h /app -g "mailu app" -s /bin/bash mailu \
  ; apk add --no-cache bash ca-certificates curl python3 supervisor tzdata py3-psycopg-pyc py3-psycopg-c-pyc py3-mysqlclient-pyc \
  ; ! [[ "$(apk --print-arch)" == x86_64 ]] \
    || apk add --no-cache --repository=http://dl-cdn.alpinelinux.org/alpine/edge/testing hardened-malloc

COPY download-github-asset /usr/local/bin/download-github-asset
RUN chmod 755 /usr/local/bin/download-github-asset

WORKDIR /app

COPY supervisor-healthcheck /usr/local/bin/supervisor-healthcheck
RUN chmod 755 /usr/local/bin/supervisor-healthcheck

CMD ["/bin/bash"]


# build virtual env (intermediate)
FROM system AS build

ARG MAILU_DEPS=prod
ARG SNUFFLEUPAGUS_VERSION=0.14.0

ENV VIRTUAL_ENV=/app/venv

COPY requirements-build.txt ./

RUN set -euxo pipefail \
  ; apk add --no-cache py3-pip \
  ; python3 -m venv ${VIRTUAL_ENV} \
  ; ${VIRTUAL_ENV}/bin/pip install --no-cache-dir -r requirements-build.txt \
  ; apk del -r py3-pip \
  ; rm -f /tmp/*.pem

COPY requirements-${MAILU_DEPS}.txt ./
COPY libs/ libs/

ENV \
  PATH="${VIRTUAL_ENV}/bin:${PATH}" \
  CXXFLAGS="-g -O2 -fdebug-prefix-map=/app=. -fstack-protector-strong -Wformat -Werror=format-security -fstack-clash-protection -fexceptions" \
  CFLAGS="-g -O2 -fdebug-prefix-map=/app=. -fstack-protector-strong -Wformat -Werror=format-security -fstack-clash-protection -fexceptions" \
  CPPFLAGS="-Wdate-time -D_FORTIFY_SOURCE=2" \
  LDFLAGS="-Wl,-z,noexecstack -Wl,-z,relro -Wl,-z,now" \
  SNUFFLEUPAGUS_URL="https://github.com/jvoisin/snuffleupagus/archive/refs/tags/v${SNUFFLEUPAGUS_VERSION}.tar.gz"

# snuffleupagus' Makefile calls the unversioned "phpize", which alpine ships
# only for its current default php -- and that moves every release. Pin both
# wrappers to the php it builds for.
RUN --mount=type=secret,id=github_token,required=false set -euxo pipefail \
  ;  machine="$(apk --print-arch)" \
  ; deps="build-base gcc libffi-dev python3-dev mariadb-dev" \
  ; [[ "${machine}" != x86_64 ]] && \
      deps="${deps} rust cargo cmake git libretls-dev mariadb-connector-c-dev" \
  ; apk add --virtual .build-deps ${deps} \
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
  ; set -x \
  # bcrypt 4.3 builds from source on arm/v7 and uses Python's stable ABI.
  ; PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 pip install -r requirements-${MAILU_DEPS}.txt \
  ; set +x \
  ; download-github-asset "${SNUFFLEUPAGUS_URL}" /tmp/snuffleupagus.tgz \
  ; mkdir -p snuffleupagus-${SNUFFLEUPAGUS_VERSION} \
  ; tar xzf /tmp/snuffleupagus.tgz --strip-components=1 -C snuffleupagus-${SNUFFLEUPAGUS_VERSION} \
  ; rm /tmp/snuffleupagus.tgz \
  ; unset github_token \
  ; set -x \
  ; cd snuffleupagus-${SNUFFLEUPAGUS_VERSION} \
  ; rm -rf src/tests/*php7*/ src/tests/*session*/ src/tests/broken_configuration/ src/tests/*cookie* src/tests/upload_validation/ \
  ; apk add --virtual .build-deps php84-dev php84-cgi php84-simplexml php84-xml pcre-dev build-base php84-pear php84-openssl re2c \
  ; ln -sf /usr/bin/phpize84 /usr/bin/phpize \
  ; ln -sf /usr/bin/php-config84 /usr/bin/php-config \
  ; pecl84 install vld-beta \
  ; make -j $(grep -c processor /proc/cpuinfo) release \
  ; cp src/.libs/snuffleupagus.so /app \
  ; rm -rf /root/.cargo /tmp/*.pem /root/.cache

# Build Alpine's Dovecot APKs with the Mailu backports. This target is used by
# front and imap only; the base image carries the signed APKs, not build tools.
FROM build AS dovecot-package-build

ARG APORTS_COMMIT=75e10f2ea64d8adbc06fcec9aea3be394f383a46
ENV PACKAGER="Mailu Dovecot Backport <dovecot-backport@mailu.io>"

RUN apk add --no-cache alpine-sdk git
RUN apk update
RUN abuild-keygen -a -n
RUN cp /root/.abuild/*.rsa.pub /etc/apk/keys/

COPY dovecot-aports/APKBUILD.patch /patches/APKBUILD.patch
COPY dovecot-aports/patches/ /patches/

RUN set -eux \
  ; git init /aports \
  ; git -C /aports remote add origin https://gitlab.alpinelinux.org/alpine/aports.git \
  ; git -C /aports fetch --depth 1 origin ${APORTS_COMMIT} \
  ; git -C /aports checkout --detach FETCH_HEAD \
  ; patch -d /aports/main/dovecot -p1 < /patches/APKBUILD.patch \
  ; cp /patches/0001-login-common-keep-post-login-fd-open.patch /aports/main/dovecot/ \
  ; cp /patches/0002-imap-empty-partial-as-quoted.patch /aports/main/dovecot/ \
  ; cd /aports/main/dovecot \
  ; REPODEST=/root/packages abuild -F -r \
  ; mkdir -p /out/front /out/imap /out/keys \
  ; arch="$(apk --print-arch)" \
  ; for package in dovecot dovecot-lua dovecot-lmtpd dovecot-pigeonhole-plugin dovecot-pop3d dovecot-submissiond dovecot-fts-flatcurve; do \
      cp "/root/packages/main/${arch}/${package}-2.4.5-r1.apk" /out/imap/; \
    done \
  ; for package in dovecot dovecot-lua dovecot-lmtpd dovecot-pigeonhole-plugin dovecot-pop3d dovecot-submissiond; do \
      cp "/out/imap/${package}-2.4.5-r1.apk" /out/front/; \
    done \
  ; cp /root/.abuild/*.rsa.pub /out/keys/

# base mailu image
FROM system

COPY --from=build /app/venv/ /app/venv/
COPY --chown=root:root --from=build /app/snuffleupagus.so /usr/lib/php84/modules/
COPY --from=dovecot-package-build /out/ /usr/share/mailu/dovecot-apks/

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
