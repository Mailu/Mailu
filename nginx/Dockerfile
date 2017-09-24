FROM alpine:edge

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --no-cache nginx nginx-mod-mail py-setuptools jinja2-cli@testing

COPY conf /conf
COPY start.sh /start.sh

CMD /start.sh
