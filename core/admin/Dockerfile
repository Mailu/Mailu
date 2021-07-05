# syntax=docker/dockerfile-upstream:1.4.3

# admin image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache libressl mariadb-connector-c postgresql-libs

COPY --from=assets /work/static/ ./mailu/static/

COPY audit.py /
COPY start.py /

<<<<<<< HEAD
COPY migrations/ ./migrations/
=======
COPY requirements-prod.txt requirements.txt
RUN apk add --no-cache libressl curl postgresql-libs mariadb-connector-c \
  && apk add --no-cache --virtual build-dep \
  libressl-dev libffi-dev python3-dev build-base postgresql-dev mariadb-connector-c-dev cargo \
  && pip3 install -r requirements.txt \
  && apk del --no-cache build-dep
>>>>>>> 3bb0d68e (add cargo to build cryptography)

COPY mailu/ ./mailu/
RUN set -euxo pipefail \
  ; venv/bin/pybabel compile -d mailu/translations

RUN echo $VERSION >/version

#EXPOSE 8080/tcp
HEALTHCHECK CMD curl -skfLo /dev/null http://localhost:8080/ping

VOLUME ["/data","/dkim"]

ENV FLASK_APP=mailu
CMD /start.py
