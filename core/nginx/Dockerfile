# syntax=docker/dockerfile-upstream:1.4.3

FROM base as static

COPY static /static

RUN set -euxo pipefail \
 && gzip -k9 /static/*.ico /static/*.txt \
 && chmod a+rX-w -R /static


FROM base

ARG VERSION
LABEL version=$VERSION

# Image specific layers under this line
RUN set -euxo pipefail \
 && apk add --no-cache certbot nginx nginx-mod-mail openssl curl \
 && pip3 install --no-cache-dir watchdog

COPY conf /conf
COPY --from=static /static /static
COPY *.py /

RUN echo $VERSION >> /version

EXPOSE 80/tcp 443/tcp 110/tcp 143/tcp 465/tcp 587/tcp 993/tcp 995/tcp 25/tcp 10025/tcp 10143/tcp
HEALTHCHECK --start-period=60s CMD curl -skfLo /dev/null http://localhost/health

VOLUME ["/certs", "/overrides"]

CMD /start.py
