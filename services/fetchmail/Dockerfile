# First stage: Build
FROM alpine:3.10 as builder

# build dependencies
RUN apk add --no-cache curl tar xz autoconf git gettext build-base openssl openssl-dev

RUN curl -L 'https://sourceforge.net/projects/fetchmail/files/branch_7-alpha/fetchmail-7.0.0-alpha6.tar.xz/download' | tar xJ
RUN cd fetchmail-7.0.0-alpha6 && \
    sed -i -e 's/SSLv3_client_method/SSLv23_client_method/' socket.c && \
    ./configure --with-ssl --prefix /usr/local --disable-nls && \
    make

FROM alpine:3.10


# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip bash \
  && pip3 install --upgrade pip

# Image specific layers under this line
RUN apk add --no-cache ca-certificates openssl \
 && pip3 install requests

COPY --from=builder /fetchmail-7.0.0-alpha6/fetchmail /usr/local/bin
COPY fetchmail.py /fetchmail.py

RUN adduser -D fetchmail
USER fetchmail

CMD ["/fetchmail.py"]
