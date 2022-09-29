# syntax=docker/dockerfile-upstream:1.4.3

FROM base

ARG VERSION=local
LABEL version=$VERSION

COPY requirements-prod.txt requirements.txt
RUN set -euxo pipefail \
 && apk add --no-cache libressl curl postgresql-libs mariadb-connector-c \
 && pip install --no-cache-dir -r requirements.txt --only-binary=:all: --no-binary=Flask-bootstrap,PyYAML,SQLAlchemy \
 || ( apk add --no-cache --virtual build-dep libressl-dev libffi-dev python3-dev build-base postgresql-dev mariadb-connector-c-dev cargo \
 && pip install -r requirements.txt \
 && apk del --no-cache build-dep )

COPY mailu ./mailu
RUN pybabel compile -d mailu/translations

COPY migrations ./migrations

COPY start.py /start.py
COPY audit.py /audit.py

COPY --from=assets /work/static ./mailu/static

RUN echo $VERSION >> /version

EXPOSE 80/tcp
HEALTHCHECK CMD curl -skfLo /dev/null http://localhost/sso/login?next=ui.index

VOLUME ["/data","/dkim"]

ENV FLASK_APP mailu
CMD /start.py
