ARG VERSION=7.7-alpine
FROM solr:$VERSION

USER root
# python3 shared with most images
RUN apk add --no-cache \
    python3 py3-pip bash curl py3-multidict py3-yarl \
  && pip3 install --upgrade pip

# Shared layer between nginx, dovecot, postfix, postgresql, rspamd, unbound, rainloop, roundcube
RUN pip3 install socrate==0.2.0

RUN mkdir -p /conf
RUN chown solr:solr /conf
USER solr


COPY start.py /start.py
COPY schema.xml /conf/schema.xml
COPY solrconfig.xml /conf/solrconfig.xml

EXPOSE 8983/tcp

CMD /start.py

HEALTHCHECK CMD curl -k -f -L http://localhost:8983/solr/ || exit 1
