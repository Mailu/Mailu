# syntax=docker/dockerfile-upstream:1.4.3

# oletools image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache netcat-openbsd libmagic libffi \
  ; curl -sLo olefy.py https://raw.githubusercontent.com/HeinleinSupport/olefy/f8aac6cc55283886d153e89c8f27fae66b1c24e2/olefy.py \
  ; chmod 755 olefy.py

RUN echo $VERSION >/version

HEALTHCHECK --start-period=60s CMD echo PING|nc -q1 127.0.0.1 11343|grep "PONG"
EXPOSE 11343/tcp

USER nobody:nobody

ENV \
    OLEFY_BINDADDRESS="0.0.0.0" \
    OLEFY_BINDPORT="11343" \
    OLEFY_OLEVBA_PATH="/app/venv/bin/olevba" \
    OLEFY_PYTHON_PATH="/app/venv/bin/python3" \
    OLEFY_TMPDIR="/dev/shm/" \
    OLEFY_MINLENGTH="300" \
    OLEFY_DEL_TMP="1" \
    OLEFY_DEL_TMP_FAILED="1"

CMD /app/olefy.py
