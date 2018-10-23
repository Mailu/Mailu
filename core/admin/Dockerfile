FROM python:3-alpine

RUN mkdir -p /app
WORKDIR /app

COPY requirements-prod.txt requirements.txt
RUN apk add --no-cache openssl curl \
 && apk add --no-cache --virtual build-dep openssl-dev libffi-dev python-dev build-base \
 && pip install -r requirements.txt \
 && apk del --no-cache build-dep

COPY mailu ./mailu
COPY migrations ./migrations
COPY manage.py .
COPY start.py /start.py

RUN pybabel compile -d mailu/translations

EXPOSE 80/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/ui || exit 1
