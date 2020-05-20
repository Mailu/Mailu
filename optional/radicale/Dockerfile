# syntax=docker/dockerfile-upstream:1.4.3

<<<<<<< HEAD
# webdav image
FROM base
=======
RUN apk add --no-cache curl bash python3 \
 && pip3 install radicale=2.1.12
>>>>>>> 45f3772c (Stick radicale to 2.1.12 version)

ARG VERSION=local
LABEL version=$VERSION

COPY radicale.conf /

RUN echo $VERSION >/version

#EXPOSE 5232/tcp
HEALTHCHECK CMD ["/bin/sh", "-c", "ps ax | grep [/]radicale.conf"]

VOLUME ["/data"]

CMD radicale -S -C /radicale.conf
