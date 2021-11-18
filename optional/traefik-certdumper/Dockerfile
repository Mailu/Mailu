FROM ldez/traefik-certs-dumper
ARG VERSION

ENV TZ Etc/UTC

LABEL version=$VERSION

RUN apk --no-cache add inotify-tools util-linux bash tzdata

COPY run.sh /

VOLUME ["/traefik"]
VOLUME ["/output"]

ENTRYPOINT ["/run.sh"]
RUN echo $VERSION >> /version