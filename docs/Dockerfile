FROM python:3-alpine

COPY requirements.txt /requirements.txt

ARG version=master
ENV VERSION=$version

RUN pip install -r /requirements.txt \
 && apk add --no-cache nginx curl \
 && mkdir /run/nginx

COPY ./nginx.conf /etc/nginx/conf.d/default.conf
COPY . /docs

RUN mkdir -p /build/$VERSION \
 && sphinx-build /docs /build/$VERSION

EXPOSE 80/tcp

CMD nginx -g "daemon off;"
