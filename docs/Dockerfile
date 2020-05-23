ARG DEBIAN_FRONTEND=noninteractive
ARG DISTRO=debian:buster-slim
FROM $DISTRO

# Minimum python3 shared with most images
RUN apt-get update && apt-get install -y --no-install-recommends \
  python3 python3-pip python3-setuptools curl \
  && rm -rf /var/lib/apt/lists \
  && pip3 install --upgrade pip

# Image specific layers under this line
COPY requirements.txt /requirements.txt

ARG version=master
ENV VERSION=$version


RUN apt-get update && apt-get install -y --no-install-recommends \
  nginx \
  && rm -rf /var/lib/apt/lists \
  && pip3 install -r /requirements.txt
# && mkdir /run/nginx

COPY ./nginx.conf /etc/nginx/sites-enabled/default
COPY . /docs

RUN mkdir -p /build/$VERSION \
 && sphinx-build -W /docs /build/$VERSION

EXPOSE 80/tcp

CMD nginx -g "daemon off;"
