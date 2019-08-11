#!/usr/bin/python3

import os, os.path
import pwd
import logging as log
import sys

if not os.path.isfile("/opt/solr/server/solr/dovecot/data/index/segments_1"):
    log.info("Could not find core data in /opt/solr/server/solr/dovecot/data, adding initial set")
    os.system("cp -R /tmp/coredata/* /opt/solr/server/solr/dovecot/data/")
    os.system("chown -R solr /opt/solr/server/solr/dovecot/data")

uid = pwd.getpwnam('solr').pw_uid
os.setresuid(uid, uid, uid)
os.execv("/opt/solr/bin/solr", ["start", "-f", "-force"])
