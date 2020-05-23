ARG DEBIAN_FRONTEND=noninteractive
ARG DISTRO=debian:buster-slim
FROM $DISTRO

# Minimum python3 shared with most images
RUN apt-get update && apt-get install -y --no-install-recommends \
  python3 python3-pip python3-setuptools curl \
  && rm -rf /var/lib/apt/lists \
  && pip3 install --upgrade pip

# Image specific layers under this line
# libclamunrar9 is in non-free
RUN sed -i /etc/apt/sources.list \
        -e "s#buster main#buster main non-free#g" \
        -e "s#buster/updates main#buster/updates main non-free#g" \
        -e "s#buster-updates main#buster-updates main non-free#g"
    
RUN apt-get update && apt-get install -y --no-install-recommends \
  clamav-daemon libclamunrar9 netcat \
  && rm -rf /var/lib/apt/lists

COPY conf /etc/clamav
COPY start.py /start.py
COPY health.sh /health.sh

EXPOSE 3310/tcp
VOLUME ["/data"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD /health.sh
