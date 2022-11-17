# syntax=docker/dockerfile-upstream:1.4.3

# admin image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache libressl mariadb-connector-c postgresql-libs

EXPOSE 80/tcp

HEALTHCHECK CMD curl -skfLo /dev/null http://localhost/sso/login

VOLUME ["/data","/dkim"]

ENV FLASK_APP=mailu

COPY --from=assets /work/static/ ./mailu/static/
COPY audit.py /
COPY start.py /
COPY migrations/ ./migrations/
COPY mailu/ ./mailu/

RUN set -euxo pipefail \
  ; venv/bin/pybabel compile -d mailu/translations

RUN echo $VERSION >/version

CMD /start.py
