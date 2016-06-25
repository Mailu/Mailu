FROM alpine

RUN apk add --update \
      clamav \
      rsyslog \
      wget \
 && rm -rf /var/cache/apk/*


COPY conf /etc/clamav
COPY start.sh /start.sh

CMD ["/start.sh"]
