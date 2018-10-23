FROM python:3-alpine

RUN apk add --no-cache fetchmail ca-certificates \
 && pip install requests

COPY fetchmail.py /fetchmail.py
USER fetchmail

CMD ["/fetchmail.py"]
