# syntax=docker/dockerfile-upstream:1.4.3

FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
 && apk add --no-cache rspamd rspamd-controller rspamd-proxy rspamd-fuzzy ca-certificates curl \
 && mkdir /run/rspamd

COPY conf/ /conf
COPY start.py /start.py

RUN echo $VERSION >> /version

EXPOSE 11332/tcp 11334/tcp 11335/tcp
HEALTHCHECK --start-period=350s CMD curl -skfLo /dev/null http://localhost:11334/

VOLUME ["/var/lib/rspamd"]

CMD /start.py
