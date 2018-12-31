FROM alpine:3.8

RUN apk --no-cache add inotify-tools jq openssl util-linux bash docker
# while not strictly documented, this script seems to always(?) support previous acme.json versions too
RUN wget https://raw.githubusercontent.com/containous/traefik/master/contrib/scripts/dumpcerts.sh -O dumpcerts.sh

VOLUME ["/traefik"]
VOLUME ["/output"]

COPY run.sh /
ENTRYPOINT ["/run.sh"]
