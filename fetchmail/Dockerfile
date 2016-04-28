FROM python:alpine

RUN apk add --update \
    fetchmail \
 && rm -rf /var/cache/apk/*

COPY fetchmail.py /fetchmail.py

RUN mkdir /var/spool/mail \
 && chown mail: /var/spool/mail
USER mail

CMD ["/fetchmail.py"]
