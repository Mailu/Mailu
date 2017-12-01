FROM alpine:edge

RUN apk add --no-cache nginx nginx-mod-mail python py-jinja2 certbot openssl

COPY conf /conf
COPY *.py /

COPY dhparam.pem /certs/dhparam.pem

CMD /start.py
