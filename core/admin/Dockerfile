# syntax=docker/dockerfile-upstream:1.4.3

# admin image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache libressl mariadb-connector-c postgresql-libs

COPY mailu/ ./mailu/
RUN set -euxo pipefail \
  ; venv/bin/pybabel compile -d mailu/translations

COPY migrations/ ./migrations/

COPY audit.py /
COPY start.py /

COPY --from=assets /work/static/ ./mailu/static/

RUN echo $VERSION >/version

EXPOSE 80/tcp
HEALTHCHECK CMD curl -skfLo /dev/null http://localhost/sso/login?next=ui.index

VOLUME ["/data","/dkim"]

ENV FLASK_APP mailu
CMD /start.py
