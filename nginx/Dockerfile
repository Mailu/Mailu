FROM alpine:edge

RUN apk add --no-cache nginx nginx-mod-mail python py-jinja2

COPY conf /conf
COPY start.py /start.py

CMD /start.py
