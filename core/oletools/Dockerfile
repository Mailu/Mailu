# syntax=docker/dockerfile-upstream:1.4.3

# oletools image
FROM base

ARG VERSION=local
LABEL version=$VERSION

ARG OLEFY_SCRIPT=https://raw.githubusercontent.com/HeinleinSupport/olefy/f8aac6cc55283886d153e89c8f27fae66b1c24e2/olefy.py
ARG OLEFY_SHA256=1f5aa58b78ca7917350135b4425e5ed4d580c7051aabed1952c6afd12d0345a0
ARG OLEFY_API_URL=https://api.github.com/repos/HeinleinSupport/olefy/contents/olefy.py?ref=f8aac6cc55283886d153e89c8f27fae66b1c24e2

RUN --mount=type=secret,id=github_token,required=false set -euxo pipefail \
  ; apk add --no-cache netcat-openbsd libmagic libffi \
  ; set +x \
  ; github_token="$(cat /run/secrets/github_token 2>/dev/null || true)" \
  ; for attempt in 1 2 3; do \
      if { \
        if [ -n "$github_token" ]; then \
          curl --fail --silent --show-error --location --connect-timeout 15 --max-time 120 --retry 3 --retry-all-errors --retry-delay 5 \
            -H "Authorization: Bearer $github_token" -H 'Accept: application/vnd.github.raw' -o olefy.py "$OLEFY_API_URL"; \
        else \
          curl --fail --silent --show-error --location --connect-timeout 15 --max-time 120 --retry 3 --retry-all-errors --retry-delay 5 -o olefy.py "$OLEFY_SCRIPT"; \
        fi; \
      } && echo "$OLEFY_SHA256  olefy.py" | sha256sum -c; then \
        break; \
      fi; \
      if [ "$attempt" -eq 3 ]; then \
        echo "Failed to download and verify olefy.py after 3 attempts" >&2; \
        exit 1; \
      fi; \
      sleep 5; \
    done \
  ; unset github_token \
  ; set -x \
  ; chmod 755 olefy.py

COPY start.py /
COPY run_olefy.py /

RUN echo $VERSION >/version
RUN touch /etc/supervisord.conf && chown nobody:nobody /etc/supervisord.conf \
  ; mkdir -p /run/mailu-supervisor && chown nobody:nobody /run/mailu-supervisor

HEALTHCHECK --start-period=60s CMD /usr/local/bin/supervisor-healthcheck && echo PING|nc -q1 127.0.0.1 11343|grep "PONG"
#EXPOSE 11343/tcp

USER nobody:nobody

ENV \
    OLEFY_BINDADDRESS="" \
    OLEFY_BINDPORT="11343" \
    OLEFY_OLEVBA_PATH="/app/venv/bin/olevba" \
    OLEFY_PYTHON_PATH="/app/venv/bin/python3" \
    OLEFY_TMPDIR="/dev/shm/" \
    OLEFY_MINLENGTH="300" \
    OLEFY_DEL_TMP="1" \
    OLEFY_DEL_TMP_FAILED="1"

CMD ["/start.py"]
