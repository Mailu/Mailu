<<<<<<< HEAD
ARG DISTRO=alpine:3.14.2
=======
ARG DISTRO=alpine:3.14.5
>>>>>>> a54a7841 (Update alpine-linux to 3.14.5 - Zlib security FIX)
FROM $DISTRO
ARG VERSION

ENV TZ Etc/UTC

LABEL version=$VERSION

# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip bash tzdata \
  && pip3 install --upgrade pip

# Image specific layers under this line
RUN apk add --no-cache fetchmail ca-certificates openssl \
 && pip3 install requests

RUN mkdir -p /data

COPY fetchmail.py /fetchmail.py

CMD ["/fetchmail.py"]
RUN echo $VERSION >> /version