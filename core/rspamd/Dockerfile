<<<<<<< HEAD
# syntax=docker/dockerfile-upstream:1.4.3
=======
ARG DISTRO=alpine:3.10
FROM $DISTRO
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip git bash py3-multidict \
  && pip3 install --upgrade pip
>>>>>>> 09ee3ce9 (Install py3-multidict from repository before installing socrate to avoid the need of gcc during build)

# rspamd image
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
  ; apk add --no-cache rspamd rspamd-controller rspamd-fuzzy rspamd-proxy \
  ; mkdir /run/rspamd \
  ; mkdir /overrides

COPY conf/ /conf/
COPY start.py /

RUN echo $VERSION >/version

#EXPOSE 11332/tcp 11334/tcp 11335/tcp
HEALTHCHECK --start-period=350s CMD curl -skfLo /dev/null http://localhost:11334/

VOLUME ["/var/lib/rspamd"]

CMD /start.py
