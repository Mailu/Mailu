ARG DEBIAN_FRONTEND=noninteractive
ARG DISTRO=debian:buster-slim
FROM $DISTRO

# Minimum python3 shared with most images
RUN apt-get update && apt-get install -y --no-install-recommends \
  python3 python3-pip python3-setuptools curl \
  && rm -rf /var/lib/apt/lists \
  && pip3 install --upgrade pip

# Image specific layers under this line
RUN pip3 install radicale==2.1.12

COPY radicale.conf /radicale.conf

EXPOSE 5232/tcp
VOLUME ["/data"]

CMD radicale -f -S -C /radicale.conf

HEALTHCHECK CMD curl -f -L http://localhost:5232/ || exit 1
