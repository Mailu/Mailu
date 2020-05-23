ARG DISTRO=debian:buster-slim
FROM $DISTRO

ARG DEBIAN_FRONTEND=noninteractive

# Minimum python3 shared with most images
RUN apt-get update && apt-get install -y --no-install-recommends \
  python3 python3-pip python3-setuptools curl \
  && rm -rf /var/lib/apt/lists \
  && pip3 install --upgrade pip

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube
RUN pip3 install socrate==0.2.0

# Image specific layers under this line
RUN groupadd -g 70 postgres \
  && useradd -g postgres -u 70 -d /var/lib/postgresql -s /bin/bash postgres

RUN apt-get update && apt-get install -y --no-install-recommends \
  cron postgresql-11 sudo libpq-dev gcc python3-dev \
  && pip3 install psycopg2 anosql==0.3.1 \
  && apt-get autoremove -y --purge libpq-dev gcc python3-dev \
  && rm -rf /var/lib/apt/lists 

COPY start.py /start.py
COPY basebackup.sh /basebackup.sh
COPY conf /conf

COPY postgres_crontab /etc/postgres_crontab
RUN crontab /etc/postgres_crontab

RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
  && locale-gen en_US.UTF-8 
ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8
  
RUN mkdir -p /data /backup /run/postgresql \
  && chown -R postgres:postgres /run/postgresql \
  && chmod 2777 /run/postgresql

VOLUME /data
VOLUME /backup
EXPOSE 5432

CMD /start.py
HEALTHCHECK CMD psql -h 127.0.0.1 -d postgres -U health -c "select 1 as ok;" || exit 1
