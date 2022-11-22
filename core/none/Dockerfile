# syntax=docker/dockerfile-upstream:1.4.3

# idle image (to dynamically replace any disabled component)
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN echo $VERSION >/version

HEALTHCHECK CMD true

USER mailu
CMD ["/bin/bash", "-c", "sleep infinity"]
