FROM ldez/traefik-certs-dumper

ENV TZ Etc/UTC

RUN apk --no-cache add inotify-tools util-linux bash tzdata

COPY run.sh /

VOLUME ["/traefik"]
VOLUME ["/output"]

ENTRYPOINT ["/run.sh"]
