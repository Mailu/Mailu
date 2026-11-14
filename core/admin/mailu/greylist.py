"""Greylist state machine backed by the shared quarantine repository."""

import math
import uuid
from datetime import datetime, timedelta, timezone
from flask import current_app

from mailu import quarantine, quarantine_repository


RETENTION = timedelta(days=quarantine_repository.GREYLIST_RETENTION_DAYS)
MAX_ENTRIES = 10000


def directory():
    """Use the same on-disk repository as long-lived quarantine records."""
    return quarantine.directory()


def _key(message_id):
    return quarantine_repository.message_key(message_id, 'greylist')


def _recipient_list(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return sorted({item.strip().lower() for item in value
                   if isinstance(item, str) and '@' in item and len(item) <= 320})


def record(metadata, raw_message=None):
    """Store a soft-rejected message or clear it after an accepted retry."""
    if not isinstance(metadata, dict):
        return None
    message_id = metadata.get('message_id') or metadata.get('message-id')
    key = _key(message_id)
    action = str(metadata.get('action', '')).strip().lower()
    if action not in {'soft reject', 'soft_reject', 'greylist'}:
        if action in {'no action', 'accept', 'add header', 'rewrite subject'}:
            if key is not None:
                quarantine_repository.delete(directory(), key, 'greylist')
        return False

    key = key or str(uuid.uuid4())
    sender = metadata.get('from') or metadata.get('sender') or ''
    subject = metadata.get('subject') or ''
    score = metadata.get('score')
    entry = {
        'message_id': message_id.strip().strip('<>').strip() if isinstance(message_id, str) else '',
        'received': datetime.now(timezone.utc).isoformat(),
        'from': sender[:512] if isinstance(sender, str) else '',
        'subject': subject[:998] if isinstance(subject, str) else '',
        'recipients': _recipient_list(metadata.get('rcpt', metadata.get('recipients', []))),
        'score': score if isinstance(score, (int, float)) and not isinstance(score, bool)
                 and math.isfinite(score) else None,
    }
    quarantine_repository.store(directory(), key, raw_message, entry, 'greylist')
    return True


def clear(metadata):
    """Remove a pending greylist copy once the message is quarantined."""
    if not isinstance(metadata, dict):
        return False
    message_id = metadata.get('message_id') or metadata.get('message-id')
    key = _key(message_id)
    if key is None:
        return False
    try:
        return quarantine_repository.delete(directory(), key, 'greylist')
    except OSError:
        current_app.logger.exception('Could not clear quarantined message from greylist')
        return False


def entries():
    """List unexpired pending messages in the shared repository."""
    quarantine_repository.cleanup_expired(
        directory(), current_app.config['QUARANTINE_RETENTION_DAYS']
    )
    return quarantine_repository.entries(directory(), kind='greylist')[:MAX_ENTRIES]


def get(record_id):
    """Return a pending greylist record and saved message when available."""
    return quarantine_repository.get(directory(), record_id, 'greylist', RETENTION.days)


def delete(record_id):
    """Remove a pending greylist record from the shared repository."""
    return quarantine_repository.delete(directory(), record_id, 'greylist')


def cleanup_expired():
    """Run shared expiration, including greylist's shorter retention."""
    return quarantine_repository.cleanup_expired(
        directory(), current_app.config['QUARANTINE_RETENTION_DAYS']
    )
