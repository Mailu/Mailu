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

EXPOSE 80/tcp
HEALTHCHECK --start-period=350s CMD curl -m3 -skfLo /dev/null http://localhost/ && /usr/local/bin/supervisor-healthcheck
USER mailu

CMD ["/start.py"]
