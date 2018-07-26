FROM alpine

RUN apk add --no-cache postfix postfix-pcre rsyslog \
    python3 py3-pip \
 && pip3 install jinja2 podop

COPY conf /conf
COPY start.py /start.py

EXPOSE 25/tcp 10025/tcp

CMD /start.py
