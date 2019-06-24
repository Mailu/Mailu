# First stage: Build
FROM alpine:3.8 as builder

# build dependencies
RUN apk add --no-cache curl tar xz autoconf git gettext build-base openssl openssl-dev

RUN curl -L 'https://netcologne.dl.sourceforge.net/project/fetchmail/branch_6.3/fetchmail-7.0.0-alpha6.tar.xz' | tar xJ
RUN cd fetchmail-7.0.0-alpha6 && \
    ./configure --with-ssl --prefix /usr/local --disable-nls && \
    make

FROM alpine:3.8


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
