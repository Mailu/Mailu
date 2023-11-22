# Convert .rst files to .html in temporary build container
FROM python:3.12.0-alpine3.18 AS build

ARG version=master
ENV VERSION=$version

COPY requirements.txt /requirements.txt
COPY . /docs

RUN apk add --no-cache --virtual .build-deps \
    gcc musl-dev \
 && pip3 install -r /requirements.txt \
 && mkdir -p /build/$VERSION \
 && sphinx-build -W /docs /build/$VERSION \
 && apk del .build-deps


# Build nginx deployment image including generated html
FROM nginx:1.25.3-alpine

ARG version=master
ARG pinned_version=master
ENV VERSION=$version
ENV TZ Etc/UTC
LABEL version=$VERSION

COPY ./nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/$VERSION /build/$VERSION

EXPOSE 80/tcp

CMD nginx -g "daemon off;"
RUN echo $pinned_version >> /version