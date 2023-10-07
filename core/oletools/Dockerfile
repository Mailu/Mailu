# syntax=docker/dockerfile-upstream:1.4.3

# oletools image
FROM base

ARG VERSION=local
LABEL version=$VERSION

ARG OLEFY_SCRIPT=https://raw.githubusercontent.com/HeinleinSupport/olefy/f8aac6cc55283886d153e89c8f27fae66b1c24e2/olefy.py
ARG OLEFY_SHA256=1f5aa58b78ca7917350135b4425e5ed4d580c7051aabed1952c6afd12d0345a0

RUN set -euxo pipefail \
  ; apk add --no-cache netcat-openbsd libmagic libffi \
  ; curl -sLo olefy.py $OLEFY_SCRIPT \
  ; echo "$OLEFY_SHA256  olefy.py" |sha256sum -c \
  ; chmod 755 olefy.py

COPY start.py /

RUN echo $VERSION >/version

HEALTHCHECK --start-period=60s CMD echo PING|nc -q1 127.0.0.1 11343|grep "PONG"
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

CMD /start.py
