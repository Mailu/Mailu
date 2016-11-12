FROM python:alpine

RUN apk add --update \
    fetchmail \
    ca-certificates \
 && rm -rf /var/cache/apk/*

COPY fetchmail.py /fetchmail.py

CMD ["/fetchmail.py"]
