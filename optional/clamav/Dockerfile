ARG DISTRO=alpine:3.12
FROM $DISTRO
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip bash \
  && pip3 install --upgrade pip
# Image specific layers under this line
RUN apk add --no-cache clamav rsyslog wget clamav-libunrar

COPY conf /etc/clamav
COPY start.py /start.py
COPY health.sh /health.sh
COPY testing.cvd.taraa /data/testing.cvd.taraa
COPY testing.cvd.tarab /data/testing.cvd.tarab
COPY testing.cvd.tarac /data/testing.cvd.tarac

RUN cat /data/testing.cvd.taraa /data/testing.cvd.tarab \ 
/data/testing.cvd.tarac > /data/testing.cvd.tar
RUN tar -xvf /data/testing.cvd.tar -C /data/
RUN rm -v /data/testing.cvd.tar

EXPOSE 3310/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD /health.sh
