# syntax=docker/dockerfile-upstream:1.4.3

<<<<<<< HEAD
# webdav image
FROM base
=======
RUN apk add --no-cache curl bash python3 \
<<<<<<< HEAD
 && pip3 install radicale=2.1.12
>>>>>>> 45f3772c (Stick radicale to 2.1.12 version)
=======
 && pip3 install radicale==2.1.12
>>>>>>> 6647c96b (Fixed typo in Dockerfile)

ARG VERSION=local
LABEL version=$VERSION

COPY radicale.conf /

RUN echo $VERSION >/version

#EXPOSE 5232/tcp
HEALTHCHECK CMD ["/bin/sh", "-c", "ps ax | grep [/]radicale.conf"]

VOLUME ["/data"]

CMD radicale -S -C /radicale.conf
