FROM alpine:3.7

RUN apk add --no-cache postfix postfix-sqlite postfix-pcre rsyslog python py-jinja2 py-pip \
 && pip install --upgrade pip \
 && pip install tenacity

COPY conf /conf
COPY start.py /start.py

EXPOSE 25/tcp 10025/tcp
VOLUME ["/data"]

CMD /start.py
