FROM alpine

RUN apk add --no-cache postfix postfix-mysql postfix-sqlite postfix-pcre rsyslog python py-jinja2 nano

COPY conf /conf
COPY start.py /start.py

CMD /start.py
