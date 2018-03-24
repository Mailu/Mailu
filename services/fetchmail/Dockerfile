FROM python:alpine

RUN apk add --no-cache fetchmail ca-certificates && \
  pip install pymysql

COPY fetchmail.py /fetchmail.py

CMD ["/fetchmail.py"]
