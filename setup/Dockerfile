ARG DISTRO=python:3.8-alpine3.14
FROM $DISTRO

RUN mkdir -p /app
WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY server.py ./server.py
COPY main.py ./main.py
COPY flavors /data/flavors
COPY templates /data/templates
COPY static ./static

EXPOSE 80/tcp

CMD gunicorn -w 4 -b :80 --access-logfile - --error-logfile - --preload main:app
