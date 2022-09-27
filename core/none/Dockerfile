# syntax=docker/dockerfile-upstream:1.4.3
# This is an idle image to dynamically replace any component if disabled.

FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN echo $VERSION >> /version

HEALTHCHECK CMD true

USER app
CMD ["/bin/bash", "-c", "sleep infinity"]
