FROM alpine:3.8

RUN apk add --no-cache nginx nginx-mod-mail python py-jinja2 certbot openssl
# added to fix #522
RUN apk add --no-cache py-requests-toolbelt py-pip
RUN pip install "idna<2.7"

COPY conf /conf
COPY *.py /

CMD /start.py
