# First stage to build assets
ARG DISTRO=debian:buster-slim
ARG ARCH=""
FROM ${ARCH}node:8 as assets
#COPY --from=balenalib/rpi-alpine:3.10 /usr/bin/qemu-arm-static /usr/bin/qemu-arm-static

COPY package.json ./
RUN npm install

COPY ./webpack.config.js ./
COPY ./assets ./assets
RUN mkdir static \
 && ./node_modules/.bin/webpack-cli


# Actual application
FROM $DISTRO
# python3 shared with most images
RUN apt-get update && apt-get install -y --no-install-recommends\
  python3 curl python3-pip git python3-multidict python3-yarl\
  python3-wheel python3-setuptools\
  && rm -rf /var/lib/apt/lists \
  && pip3 install --upgrade pip

RUN mkdir -p /app
WORKDIR /app

COPY requirements-prod.txt requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends\
  libssl-dev libmariadb-dev-compat libpq-dev gcc libffi-dev python3-dev\
  && pip3 install -r requirements.txt\
  && apt-get remove -y --purge libssl-dev libmariadb-dev-compat libpq-dev gcc libffi-dev python3-dev\
  && apt-get autoremove -y\
  && rm -rf /var/lib/apt/lists

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
