ARG DISTRO=alpine:3.14
FROM $DISTRO

# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip bash \
  && pip3 install --upgrade pip

# Image specific layers under this line
RUN apk add --no-cache fetchmail ca-certificates openssl \
 && pip3 install requests

COPY fetchmail.py /fetchmail.py

USER fetchmail

CMD ["/fetchmail.py"]
