FROM alpine

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories \
 && apk add --update \
      perl-socket6 \
      perl-io-socket-inet6@testing \
      amavisd-new \
      spamassassin \
      rsyslog \
      wget \
 && rm -rf /var/cache/apk/*

COPY conf /etc/
COPY rsyslog.conf /etc/rsyslog.conf

COPY start.sh /start.sh

CMD ["/start.sh"]
