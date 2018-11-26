FROM alpine:3.8
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip \
  && pip3 install --upgrade pip
# Shared layer between rspamd, postfix, dovecot, unbound and nginx
RUN pip3 install jinja2
# Image specific layers under this line
RUN apk add --no-cache certbot nginx nginx-mod-mail openssl curl \
 && pip3 install idna requests

COPY conf /conf
COPY *.py /

EXPOSE 80/tcp 443/tcp 110/tcp 143/tcp 465/tcp 587/tcp 993/tcp 995/tcp 25/tcp 10025/tcp 10143/tcp
VOLUME ["/certs"]
VOLUME ["/overrides"]

CMD /start.py

HEALTHCHECK CMD curl -k -f -L http://localhost/health || exit 1
