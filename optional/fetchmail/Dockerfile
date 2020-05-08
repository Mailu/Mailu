ARG DISTRO=debian:buster-slim
FROM $DISTRO

ARG DEBIAN_FRONTEND=noninteractive

# Minimum python3 shared with most images
RUN apt-get update && apt-get install -y --no-install-recommends \
  python3 python3-pip python3-setuptools curl \
  && rm -rf /var/lib/apt/lists \
  && pip3 install --upgrade pip

# Image specific layers under this line
RUN pip3 install requests
# We want fetchmail>=6.4.2 (ssl wrapped mode autoprobe)
# buster only provides 6.4.0
RUN echo "deb http://deb.debian.org/debian bullseye main" >> /etc/apt/sources.list \
  && apt-get update && apt-get install -y --no-install-recommends \
  fetchmail libssl1.1 openssl netbase ca-certificates \
  && rm -rf /var/lib/apt/lists

COPY fetchmail.py /fetchmail.py

USER fetchmail

CMD ["/fetchmail.py"]
