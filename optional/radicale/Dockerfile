FROM alpine:3.10

RUN apk add --no-cache curl bash python3 \
 && pip3 install radicale==2.1.12

COPY radicale.conf /radicale.conf

EXPOSE 5232/tcp
VOLUME ["/data"]

CMD radicale -f -S -C /radicale.conf

HEALTHCHECK CMD curl -f -L http://localhost:5232/ || exit 1
