# syntax=docker/dockerfile-upstream:1.4.3

# setup image
FROM base

ARG VERSION=local
LABEL version=$VERSION

COPY flavors /data/flavors
COPY templates /data/templates
COPY static ./static
COPY server.py ./server.py
COPY main.py ./main.py
COPY start.py /start.py

RUN echo $VERSION >> /version
# The setup image runs as mailu, so prepare the paths used by socrate's
# unprivileged supervisor before switching users.
RUN touch /etc/supervisord.conf && chown mailu:mailu /etc/supervisord.conf \
  ; mkdir -p /run/mailu-supervisor && chown mailu:mailu /run/mailu-supervisor

EXPOSE 80/tcp
HEALTHCHECK --start-period=350s CMD /usr/local/bin/supervisor-healthcheck && curl -m3 -skfLo /dev/null http://localhost/
USER mailu

CMD ["/start.py"]
