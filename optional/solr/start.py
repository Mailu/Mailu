#!/usr/bin/python3

import os
import logging as log
import sys

from socrate import conf

log.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "WARNING"))

os.execv("/opt/docker-solr/scripts/solr-precreate", ["solr-precreate", "dovecot"])
os.remove("/opt/solr/server/solr/mycores/dovecot/conf/managed-schema")

for solr_file in glob.glob("/conf/*.xml"):
    conf.jinja(solr_file, os.environ, os.path.join("/opt/solr/server/solr/mycores/dovecot/conf/", os.path.basename(solr_file)))

os.execv("/opt/docker-solr/scripts/solr-foreground", ["solr-foreground"])
