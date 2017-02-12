FROM python:alpine

RUN apk add --no-cache fetchmail ca-certificates

COPY fetchmail.py /fetchmail.py

CMD ["/fetchmail.py"]
