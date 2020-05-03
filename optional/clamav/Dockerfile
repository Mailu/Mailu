ARG DISTRO=debian:buster-slim
FROM $DISTRO

RUN apt-get update && apt-get install -y \
  python3 clamav-daemon rsyslog netcat \
  && rm -rf /var/lib/apt/lists

COPY conf /etc/clamav
COPY start.py /start.py
COPY health.sh /health.sh

EXPOSE 3310/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD /health.sh
