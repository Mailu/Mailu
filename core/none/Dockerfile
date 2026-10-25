# syntax=docker/dockerfile-upstream:1.4.3

# idle image (to dynamically replace any disabled component)
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN echo $VERSION >/version

COPY start.py /

HEALTHCHECK CMD /usr/local/bin/supervisor-healthcheck

USER mailu
CMD ["/start.py"]
