# syntax=docker/dockerfile-upstream:1.4.3

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

# To be removed once https://gitlab.alpinelinux.org/alpine/aports/-/issues/16914 is resolved
RUN sed -i '179,185d' /etc/rspamd/modules.d/rbl.conf
RUN sed -i '384,388d' /etc/rspamd/scores.d/rbl_group.conf

RUN echo $VERSION >/version

#EXPOSE 11332/tcp 11334/tcp 11335/tcp
HEALTHCHECK --start-period=350s CMD curl -m3 -skfLo /dev/null http://localhost:11334/

VOLUME ["/var/lib/rspamd"]

CMD /start.py
