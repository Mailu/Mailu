FROM alpine

RUN apk add --update \
      clamav \
      rsyslog \
      wget \
 && rm -rf /var/cache/apk/*


COPY conf /etc/clamav


CMD ["/usr/sbin/clamd"]
