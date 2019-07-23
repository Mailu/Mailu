# First stage to build assets
FROM node:8 as assets

COPY package.json ./
RUN npm install

COPY ./webpack.config.js ./
COPY ./assets ./assets
RUN mkdir static \
 && ./node_modules/.bin/webpack-cli


# Actual application
FROM alpine:3.10
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip git bash \
  && pip3 install --upgrade pip

RUN mkdir -p /app
WORKDIR /app

COPY requirements-prod.txt requirements.txt
RUN apk add --no-cache libressl curl postgresql-libs mariadb-connector-c \
  && apk add --no-cache --virtual build-dep \
  libressl-dev libffi-dev python3-dev build-base postgresql-dev mariadb-connector-c-dev \
  && pip3 install -r requirements.txt \
  && apk del --no-cache build-dep

COPY --from=assets static ./mailu/ui/static
COPY mailu ./mailu
COPY migrations ./migrations
COPY start.py /start.py

RUN pybabel compile -d mailu/translations

EXPOSE 80/tcp
VOLUME ["/data","/dkim"]
ENV FLASK_APP mailu

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/ui/login?next=ui.index || exit 1

