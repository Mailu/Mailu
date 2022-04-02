ARG DISTRO=alpine:3.14.5
FROM $DISTRO
ARG VERSION
ENV TZ Etc/UTC
LABEL version=$VERSION


RUN mkdir -p /app
WORKDIR /app

COPY requirements.txt requirements.txt
RUN apk add --no-cache curl python3 py3-pip \
    && pip3 install -r requirements.txt

COPY server.py ./server.py
COPY main.py ./main.py
COPY flavors /data/flavors
COPY templates /data/templates
COPY static ./static

EXPOSE 80/tcp

CMD gunicorn -w 4 -b :80 --access-logfile - --error-logfile - --preload main:app
RUN echo $VERSION >> /version
