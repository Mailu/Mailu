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

RUN echo $VERSION >> /version

#Note: This is appended so we can explicitly check if this JS file has been loaded
#by the user's internet browser when accessing the setup site.
RUN echo var jQueryMailu=\'loaded\'\; >> ./static/jquery.min.js

EXPOSE 80/tcp
HEALTHCHECK --start-period=350s CMD curl -skfLo /dev/null http://localhost/
USER mailu

CMD gunicorn -w 4 -b :80 --access-logfile - --error-logfile - --preload main:app
