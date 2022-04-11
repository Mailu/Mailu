# syntax=docker/dockerfile-upstream:1.4.3

# webdav image
FROM base

ARG VERSION=local
LABEL version=$VERSION

COPY radicale.conf /

<<<<<<< HEAD
RUN echo $VERSION >/version
=======
# Image specific layers under this line
RUN apk add --no-cache curl \
 && pip3 install pytz radicale~=3.0
>>>>>>> bb0a96c6 (Add pytz module)

#EXPOSE 5232/tcp
HEALTHCHECK CMD ["/bin/sh", "-c", "ps ax | grep [/]radicale.conf"]

VOLUME ["/data"]

CMD radicale -S -C /radicale.conf
<<<<<<< HEAD
=======

HEALTHCHECK CMD curl -f -L http://localhost:5232/ || exit 1
RUN echo $VERSION >> /version
>>>>>>> bb0a96c6 (Add pytz module)
