FROM alpine:3.8
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip \
  && pip3 install --upgrade pip
# Shared layer between rspamd, postfix, dovecot, unbound and nginx
RUN pip3 install jinja2
# Image specific layers under this line
RUN apk add --no-cache \
    postgresql postgresql-libs postgresql-contrib \
  && apk add --virtual .build-deps gcc musl-dev postgresql-dev python3-dev \
  && pip3 install psycopg2 anosql \
  && apk --purge del .build-deps

COPY start.py /start.py
COPY conf /conf

ENV LANG en_US.UTF-8

RUN mkdir -p /var/lib/postgresql/data /run/postgresql \
  && chown -R postgres:postgres /var/lib/postgresql/data /run/postgresql \
  && chmod 2777 /run/postgresql

VOLUME /var/lib/postgresql/data
EXPOSE 5432

CMD /start.py
