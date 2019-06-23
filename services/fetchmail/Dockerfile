FROM alpine:3.9
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip bash \
  && pip3 install --upgrade pip
# Image specific layers under this line
RUN apk add --no-cache fetchmail ca-certificates \
 && pip3 install requests

COPY fetchmail.py /fetchmail.py
USER fetchmail

CMD ["/fetchmail.py"]
