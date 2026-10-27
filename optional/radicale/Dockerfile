# syntax=docker/dockerfile-upstream:1.4.3

# webdav image
FROM base

ARG VERSION=local
LABEL version=$VERSION

COPY radicale.conf /
COPY start.py /

RUN echo $VERSION >/version

#EXPOSE 5232/tcp
HEALTHCHECK CMD /usr/local/bin/supervisor-healthcheck

VOLUME ["/data"]

CMD ["/start.py"]
