# syntax=docker/dockerfile-upstream:1.4.3

# idle image (to dynamically replace any disabled component)
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN echo $VERSION >/version

HEALTHCHECK CMD true

USER mailu
CMD ["env", "-i", "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "/bin/sleep", "infinity"]
