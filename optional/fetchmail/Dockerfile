ARG DISTRO=alpine:3.14.2
FROM $DISTRO

ENV TZ Etc/UTC

# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip bash tzdata \
  && pip3 install --upgrade pip

# Image specific layers under this line
RUN apk add --no-cache fetchmail ca-certificates openssl \
 && pip3 install requests

COPY fetchmail.py /fetchmail.py

USER fetchmail

CMD ["/fetchmail.py"]
