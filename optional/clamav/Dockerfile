FROM alpine:3.10
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip bash \
  && pip3 install --upgrade pip
# Image specific layers under this line
RUN apk add --no-cache clamav rsyslog wget clamav-libunrar

COPY conf /etc/clamav
COPY start.py /start.py
COPY health.sh /health.sh

EXPOSE 3310/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD /health.sh
