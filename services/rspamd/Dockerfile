FROM alpine:edge

RUN apk add --no-cache rspamd ca-certificates

RUN mkdir /run/rspamd

COPY conf/ /etc/rspamd

CMD ["rspamd", "-i", "-f"]
