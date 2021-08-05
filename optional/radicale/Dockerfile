ARG DISTRO=alpine:3.14
FROM $DISTRO

# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip bash \
  && pip3 install --upgrade pip

# Image specific layers under this line
RUN apk add --no-cache curl \
 && pip3 install radicale~=3.0


COPY radicale.conf /radicale.conf

EXPOSE 5232/tcp
VOLUME ["/data"]

CMD radicale -S -C /radicale.conf

HEALTHCHECK CMD curl -f -L http://localhost:5232/ || exit 1
