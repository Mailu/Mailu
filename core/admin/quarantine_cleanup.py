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
next_cleanup = time.monotonic()

with application.app_context():
    while True:
        # Poll on UTC hour boundaries so delivery timing does not drift with
        # container starts or with the duration of the cleanup work.
        time.sleep(max(1, 3600 - (time.time() % 3600)))
        if time.monotonic() >= next_cleanup:
            removed = cleanup_expired(retention_days)
            if removed:
                logging.info('Removed %d expired quarantine and greylist records', removed)
            next_cleanup = time.monotonic() + 86400
        try:
            sent = quarantine.send_due_summaries()
            if sent:
                logging.info('Sent %d quarantine summary emails', sent)
        except Exception:
            logging.exception('Could not send quarantine summary emails')
