ARG DEBIAN_FRONTEND=noninteractive
ARG DISTRO=debian:buster-slim
FROM $DISTRO

# python3 shared with most images
RUN apt-get update && apt-get install -y --no-install-recommends \
  python3 python3-pip python3-setuptools curl \
  && rm -rf /var/lib/apt/lists \
  && pip3 install --upgrade pip

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube
RUN pip3 install socrate==0.2.0

# Shared layer between dovecot and postfix
RUN apt-get update && apt-get install -y --no-install-recommends \
  python3-multidict python3-yarl \
  && rm -rf /var/lib/apt/lists \  
  && pip3 install "podop>0.2.5"

# Image specific layers under this line
RUN apt-get update && apt-get install -y --no-install-recommends \
  postfix postfix-pcre sasl2-bin libsasl2-modules netcat \
  && rm -rf /var/lib/apt/lists  

COPY conf /conf
COPY start.py /start.py

EXPOSE 25/tcp 10025/tcp
VOLUME ["/queue"]

CMD /start.py

HEALTHCHECK --start-period=350s CMD echo QUIT|nc localhost 25|grep "220 .* ESMTP Postfix"
