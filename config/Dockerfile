FROM python:3-alpine

RUN mkdir -p /app
WORKDIR /app

COPY requirements.txt requirements.txt
RUN apk add --no-cache git \
 && pip install -r requirements.txt

COPY server.py ./server.py
COPY setup.py ./setup.py
COPY main.py ./main.py

RUN python setup.py https://github.com/mailu/mailu /data

EXPOSE 80/tcp

CMD gunicorn -w 4 -b 0.0.0.0:80 -b [::]:80 --access-logfile - --error-logfile - --preload main:app
