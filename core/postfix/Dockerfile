FROM alpine:3.7

RUN apk add --no-cache postfix postfix-sqlite postfix-pcre rsyslog python py-jinja2

COPY conf /conf
COPY start.py /start.py

EXPOSE 25/tcp 10025/tcp

CMD /start.py
