FROM alpine

RUN apk add --no-cache postfix postfix-sqlite postfix-pcre rsyslog python py-jinja2

COPY conf /conf
COPY start.py /start.py

CMD /start.py
