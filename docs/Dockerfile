FROM python:3-alpine

RUN apk add --no-cache git

COPY docs/requirements.txt requirements.txt
RUN pip install -r /requirements.txt \
 && mkdir /src

WORKDIR /src
COPY .git /src/.git

RUN sphinx-versioning build -b -B 1.5 -r 1.5 -w '^[0-9.]*$' -w master -W '^$' /src /build

