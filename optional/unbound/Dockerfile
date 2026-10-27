# syntax=docker/dockerfile-upstream:1.4.3

# resolver image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache bind-tools unbound \
  ; curl -so /etc/unbound/root.hints https://www.internic.net/domain/named.cache \
  ; chown root:unbound /etc/unbound \
  ; chmod 775 /etc/unbound \
  ; /usr/sbin/unbound-anchor -a /etc/unbound/trusted-key.key || true

COPY unbound.conf /
COPY start.py /

RUN echo $VERSION >/version

#EXPOSE 53/udp 53/tcp
# dig exits 0 whatever the answer, SERVFAIL included, so `dig @127.0.0.1`
# alone kept the container healthy while it failed every lookup (a stale
# DNSSEC trust anchor after the 2026 root KSK rollover). The root NS set
# goes through validation, so a broken anchor or no upstream fails this.
HEALTHCHECK CMD dig @127.0.0.1 +time=3 +tries=1 . NS | grep -q 'status: NOERROR' && /usr/local/bin/supervisor-healthcheck

CMD ["/start.py"]
