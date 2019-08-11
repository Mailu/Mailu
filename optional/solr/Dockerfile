FROM alpine:3.10
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip git bash \
  && pip3 install --upgrade pip

# Image specific layers under this line
RUN apk add --no-cache bash openjdk11-jre
COPY start.py /start.py

RUN wget -q -O- http://apache.mirror.digionline.de/lucene/solr/8.2.0/solr-8.2.0.tgz | tar xz -C /tmp
RUN mv /tmp/solr-8.2.0/ /opt/solr
RUN adduser -S -D solr
ADD conf/dovecot/ /opt/solr/server/solr/dovecot/
ADD conf/coredata /tmp/coredata

RUN chown -R solr /opt/solr

EXPOSE 8983/tcp
VOLUME /opt/solr/server/solr/dovecot/data

CMD /start.py

HEALTHCHECK --start-period=350s CMD /opt/solr/bin/solr status | grep -q "Found 1 Solr nodes"
