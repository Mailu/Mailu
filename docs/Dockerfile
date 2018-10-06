FROM python:3-alpine

COPY requirements.txt /requirements.txt

RUN pip install -r /requirements.txt \
 && apk add --no-cache nginx \
 && mkdir /run/nginx

COPY ./nginx.conf /etc/nginx/conf.d/default.conf
COPY . /docs

RUN sphinx-build /docs /build

CMD nginx -g "daemon off;"