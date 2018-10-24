FROM alpine:3.8

RUN apk add --no-cache certbot nginx nginx-mod-mail openssl curl \
 python py-jinja2 py-requests-toolbelt py-pip \
 && pip install --upgrade pip \
 && pip install idna

COPY conf /conf
COPY *.py /

EXPOSE 80/tcp 443/tcp 110/tcp 143/tcp 465/tcp 587/tcp 993/tcp 995/tcp 25/tcp 10025/tcp 10143/tcp
VOLUME ["/certs"]

CMD /start.py

HEALTHCHECK CMD curl -k -f -L http://localhost/health || exit 1
