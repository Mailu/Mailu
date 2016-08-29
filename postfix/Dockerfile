FROM alpine

RUN apk add --update bash postfix postfix-sqlite postfix-pcre rsyslog && rm -rf /var/cache/apk/*

COPY conf /etc/postfix
COPY rsyslog.conf /etc/rsyslog.conf

COPY start.sh /start.sh

CMD ["/start.sh"]
