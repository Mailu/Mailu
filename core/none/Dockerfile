# syntax=docker/dockerfile-upstream:1.4.3

# idle image (to dynamically replace any disabled component)
FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN echo $VERSION >/version
RUN touch /etc/supervisord.conf && chown mailu:mailu /etc/supervisord.conf \
  ; mkdir -p /run/mailu-supervisor && chown mailu:mailu /run/mailu-supervisor

COPY start.py /

HEALTHCHECK CMD /usr/local/bin/supervisor-healthcheck

USER mailu
CMD ["/start.py"]
