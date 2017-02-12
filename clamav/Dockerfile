FROM alpine

RUN apk add --no-cache clamav rsyslog wget

COPY conf /etc/clamav
COPY start.sh /start.sh

CMD ["/start.sh"]
