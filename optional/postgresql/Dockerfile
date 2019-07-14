FROM alpine:3.10
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip bash \
  && pip3 install --upgrade pip
# Shared layer between rspamd, postfix, dovecot, unbound, rainloop, roundcube and nginx
RUN pip3 install jinja2
# Image specific layers under this line
RUN apk add --no-cache \
    postgresql postgresql-libs busybox-suid sudo tar \
  && apk add --virtual .build-deps gcc musl-dev postgresql-dev python3-dev \
  && pip3 install psycopg2 anosql==0.3.1 \
  && apk --purge del .build-deps

COPY start.py /start.py
COPY basebackup.sh /basebackup.sh
COPY conf /conf

COPY postgres_crontab /etc/postgres_crontab
RUN crontab /etc/postgres_crontab

ENV LANG en_US.UTF-8

RUN mkdir -p /data /backup /run/postgresql \
  && chown -R postgres:postgres /run/postgresql \
  && chmod 2777 /run/postgresql

VOLUME /data
VOLUME /backup
EXPOSE 5432

CMD /start.py
HEALTHCHECK CMD psql -h 127.0.0.1 -d postgres -U health -c "select 1 as ok;" || exit 1
