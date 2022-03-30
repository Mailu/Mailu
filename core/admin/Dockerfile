<<<<<<< HEAD
# syntax=docker/dockerfile-upstream:1.4.3
=======
# First stage to build assets
ARG DISTRO=alpine:3.14.5
ARG ARCH=""
>>>>>>> a54a7841 (Update alpine-linux to 3.14.5 - Zlib security FIX)

# admin image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache libressl mariadb-connector-c postgresql-libs

COPY --from=assets /work/static/ ./mailu/static/

COPY audit.py /
COPY start.py /

COPY migrations/ ./migrations/

COPY mailu/ ./mailu/
RUN set -euxo pipefail \
  ; venv/bin/pybabel compile -d mailu/translations

RUN echo $VERSION >/version

#EXPOSE 8080/tcp
HEALTHCHECK CMD curl -skfLo /dev/null http://localhost:8080/ping

VOLUME ["/data","/dkim"]

ENV FLASK_APP=mailu
CMD /start.py
