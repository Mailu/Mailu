FROM python:3-alpine

RUN apk add --no-cache clamav rsyslog wget clamav-libunrar

COPY conf /etc/clamav
COPY start.py /start.py
COPY health.sh /health.sh

EXPOSE 3310/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK CMD /health.sh
