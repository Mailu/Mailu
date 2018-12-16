FROM python:3-alpine

RUN mkdir -p /app
WORKDIR /app

COPY requirements.txt requirements.txt
RUN apk add --no-cache curl \
 && pip install -r requirements.txt

COPY server.py ./server.py
COPY main.py ./main.py
COPY flavors /data/flavors
COPY templates /data/templates
COPY static ./static

EXPOSE 80/tcp

CMD gunicorn -w 4 -b :80 --access-logfile - --error-logfile - --preload main:app
