ARG DISTRO=python:3.8-alpine3.14
FROM $DISTRO

COPY requirements.txt /requirements.txt

ARG version=master
ENV VERSION=$version

RUN apk add --no-cache nginx curl \
 && pip3 install -r /requirements.txt

COPY ./nginx.conf /etc/nginx/conf.d/default.conf
COPY . /docs

RUN mkdir -p /build/$VERSION \
 && sphinx-build -W /docs /build/$VERSION

EXPOSE 80/tcp

CMD nginx -g "daemon off;"
