# syntax=docker/dockerfile-upstream:1.4.3

FROM base

ARG VERSION=local
LABEL version=$VERSION

RUN set -euxo pipefail \
 && apk add --no-cache postfix postfix-pcre cyrus-sasl-login rsyslog logrotate \
 && pip install --no-cache-dir --only-binary=:all: postfix-mta-sts-resolver==1.0.1 \
 || ( apk add --no-cache --virtual .build-deps gcc musl-dev python3-dev py3-wheel libffi-dev \
      && pip3 install postfix-mta-sts-resolver==1.0.1 \
      && apk del .build-deps )

COPY conf /conf
COPY start.py /start.py

RUN echo $VERSION >> /version

EXPOSE 25/tcp 10025/tcp
HEALTHCHECK --start-period=350s CMD echo QUIT|nc localhost 25|grep "220 .* ESMTP Postfix"

VOLUME ["/queue"]

CMD /start.py
