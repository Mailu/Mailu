# syntax=docker/dockerfile-upstream:1.4.3

<<<<<<< HEAD
# idle image (to dynamically replace any disabled component)
FROM base
=======
ARG DISTRO=alpine:3.14.5
FROM $DISTRO
>>>>>>> a54a7841 (Update alpine-linux to 3.14.5 - Zlib security FIX)

ARG VERSION=local
LABEL version=$VERSION

RUN echo $VERSION >/version

HEALTHCHECK CMD true

USER mailu
CMD ["/bin/bash", "-c", "sleep infinity"]
