FROM traefik:alpine

RUN apk add --no-cache bash

COPY conf /conf
COPY start.sh /start.sh

CMD /start.sh
