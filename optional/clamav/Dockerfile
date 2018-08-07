FROM alpine:3.7

RUN apk add --no-cache clamav rsyslog wget clamav-libunrar

COPY conf /etc/clamav
COPY start.sh /start.sh

CMD ["/start.sh"]
