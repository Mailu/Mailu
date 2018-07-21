FROM alpine:3.8

RUN apk add --no-cache nginx nginx-mod-mail python py-jinja2 certbot openssl

COPY conf /conf
COPY *.py /

CMD /start.py
