# syntax=docker/dockerfile-upstream:1.4.3

# rspamd image
FROM base

ENV RSPAMD_VERSION="3.14.2"

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache openssl-dev glib-dev ragel luajit-dev cmake sqlite-dev file-dev icu-dev pcre2-dev \
    vectorscan-dev zlib-dev jemalloc-dev libsodium-dev libarchive-dev curl-dev elfutils-dev hiredis-dev \
    libstemmer-dev libunwind-dev fasttext-dev fmt-dev xxhash-dev zstd-dev git gcc g++ make curl openssl glib luajit sqlite-libs \
    libmagic icu-libs icu-data-full pcre2 vectorscan zlib jemalloc libsodium libarchive libunwind perl \
    redis brotli-libs fann xxhash zstd-libs fasttext-libs libstemmer libdw \
  ; curl -sL https://github.com/rspamd/rspamd/archive/refs/tags/${RSPAMD_VERSION}.tar.gz | tar -xz \
  ; mv rspamd-${RSPAMD_VERSION} rspamd \
  ; mkdir rspamd.build \
    ; cd rspamd.build \
    ; cmake ../rspamd -DENABLE_HYPERSCAN=ON -DENABLE_JEMALLOC=ON -DNO_SHARED=OFF -DINSTALL_EXAMPLES=OFF \
        -DCMAKE_INSTALL_PREFIX=/usr -DCONFDIR=/etc/rspamd -DCMAKE_BUILD_TYPE=MinSizeRel -DCMAKE_INSTALL_PREFIX=/usr \
        -DCONFDIR=/etc/rspamd -DRUNDIR=/run/rspamd -DRSPAMD_USER=rspamd -DRSPAMD_GROUP=rspamd -DENABLE_FASTTEXT=ON \
        -DSYSTEM_FMT=OFF -DENABLE_PCRE2=ON -DENABLE_URL_INCLUDE=ON -DSYSTEM_XXHASH=ON -DSYSTEM_ZSTD=ON \
    ; make \
    ; make install \
    ; cd .. \
    ; rm -rf rspamd/ /rspamd.build/ \
  ; apk del openssl-dev glib-dev ragel luajit-dev cmake sqlite-dev file-dev icu-dev pcre2-dev \
    vectorscan-dev zlib-dev jemalloc-dev libsodium-dev libarchive-dev curl-dev elfutils-dev hiredis-dev \
    libunwind-dev fasttext-dev fmt-dev xxhash-dev zstd-dev git gcc g++ make \
  ; mkdir /run/rspamd /overrides \
  ; mkdir -p /var/log/rspamd /var/lib/rspamd /etc/rspamd/local.d/maps.d \
  ; addgroup -S rspamd 2>/dev/null \
  ; adduser -S -D -H -h /var/lib/rspamd -s /sbin/nologin -G rspamd -g rspamd rspamd 2>/dev/null \
  ; chown rspamd:rspamd /var/log/rspamd /var/lib/rspamd /etc/rspamd/local.d /etc/rspamd/local.d/maps.d \
  ; chmod 750 /var/log/rspamd /var/lib/rspamd /etc/rspamd/local.d \
  ; chmod 755 /etc/rspamd/local.d/maps.d

COPY conf/ /conf/
COPY start.py /

RUN echo $VERSION >/version

#EXPOSE 11332/tcp 11334/tcp 11335/tcp
HEALTHCHECK --start-period=350s CMD curl -m3 -skfLo /dev/null http://localhost:11334/

VOLUME ["/var/lib/rspamd"]

CMD /start.py
