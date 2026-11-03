#!/usr/bin/env python3

import logging
import os
import sys
import time

from mailu import create_app, quarantine
from mailu.quarantine import cleanup_expired


logging.basicConfig(stream=sys.stderr, level=os.environ.get('LOG_LEVEL', 'INFO'))
retention_days = int(os.environ.get('QUARANTINE_RETENTION_DAYS', '90'))
application = create_app()

with application.app_context():
    while True:
        removed = cleanup_expired(retention_days)
        if removed:
            logging.info('Removed %d expired quarantine and greylist records', removed)
        try:
            sent = quarantine.send_due_summaries()
            if sent:
                logging.info('Sent %d quarantine summary emails', sent)
        except Exception:
            logging.exception('Could not send quarantine summary emails')
        time.sleep(86400)
