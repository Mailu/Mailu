"""Shared file repository for rejected and temporarily greylisted messages."""

import json
import logging
import os
import re
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


GREYLIST_RETENTION_DAYS = 7
_MESSAGE_ID_KEY = re.compile(r'^[0-9a-f]{64}$')


def _kind(metadata):
    return metadata.get('kind', 'quarantine') if isinstance(metadata, dict) else None


def _record_id(value):
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        return value if _MESSAGE_ID_KEY.fullmatch(value) else None


def store(root, record_id, raw_message, metadata, kind):
    """Atomically save a message and metadata under a validated shared ID."""
    record_id = _record_id(record_id)
    if record_id is None or kind not in {'quarantine', 'greylist'}:
        raise ValueError('invalid quarantine record identity')
    if kind == 'quarantine' and not _is_uuid(record_id):
        raise ValueError('invalid quarantine UUID')
    if kind == 'greylist' and not _MESSAGE_ID_KEY.fullmatch(record_id):
        raise ValueError('invalid greylist key')
    if kind == 'quarantine' and (not isinstance(raw_message, bytes) or not raw_message):
        raise ValueError('message content is invalid')
    if raw_message is not None and not isinstance(raw_message, bytes):
        raise ValueError('message content is invalid')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    record = dict(metadata)
    record['kind'] = kind
    record['received'] = record.get('received') or time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    message_path = root / f'{record_id}.eml'
    metadata_path = root / f'{record_id}.json'
    fd_meta, temporary_metadata = tempfile.mkstemp(prefix='.quarantine-metadata-', dir=root)
    temporary_message = None
    try:
        if raw_message is not None:
            fd, temporary_message = tempfile.mkstemp(prefix='.quarantine-message-', dir=root)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw_message)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary_message, 0o600)
        with os.fdopen(fd_meta, 'w', encoding='utf-8') as stream:
            json.dump(record, stream, ensure_ascii=True, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_metadata, 0o600)
        if temporary_message is not None:
            os.replace(temporary_message, message_path)
        os.replace(temporary_metadata, metadata_path)
    finally:
        for temporary in (temporary_message, temporary_metadata):
            if temporary is None:
                continue
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
    return record_id


def _is_uuid(value):
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def _expired(metadata_path, metadata, retention_days, kind):
    if kind == 'quarantine':
        return metadata_path.stat().st_mtime < time.time() - retention_days * 86400
    try:
        received = datetime.fromisoformat(str(metadata['received']).replace('Z', '+00:00'))
        if received.tzinfo is None:
            received = received.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - received > timedelta(days=retention_days)
    except (KeyError, TypeError, ValueError):
        return True


def cleanup_expired(root, quarantine_retention_days, greylist_retention_days=GREYLIST_RETENTION_DAYS):
    """Expire both record kinds according to their own retention periods."""
    if not root.exists():
        return 0
    removed = 0
    for metadata_path in root.glob('*.json'):
        try:
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            kind = _kind(metadata)
            retention_days = (quarantine_retention_days if kind == 'quarantine'
                              else greylist_retention_days if kind == 'greylist' else 0)
            if not retention_days or _expired(metadata_path, metadata, retention_days, kind):
                metadata_path.with_suffix('.eml').unlink(missing_ok=True)
                metadata_path.unlink(missing_ok=True)
                removed += 1
        except (OSError, ValueError, TypeError):
            logging.getLogger(__name__).warning(
                'Removing invalid quarantine record %s', metadata_path.name
            )
            metadata_path.with_suffix('.eml').unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
    for message_path in root.glob('*.eml'):
        if not message_path.with_suffix('.json').exists():
            message_path.unlink(missing_ok=True)
            removed += 1
    return removed


def entries(root, kind=None):
    """Return stored records, optionally restricted to one kind."""
    results = []
    for metadata_path in root.glob('*.json'):
        try:
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            record_kind = _kind(metadata)
            if record_kind not in {'quarantine', 'greylist'} or (kind and record_kind != kind):
                continue
            message_path = metadata_path.with_suffix('.eml')
            if record_kind == 'quarantine' and not message_path.is_file():
                continue
            metadata['kind'] = record_kind
            metadata['id'] = metadata_path.stem
            if message_path.is_file():
                metadata['size'] = message_path.stat().st_size
            if record_kind == 'greylist':
                metadata['greylisted'] = True
            results.append(metadata)
        except (OSError, ValueError, TypeError):
            logging.getLogger(__name__).warning(
                'Ignoring invalid quarantine record %s', metadata_path.name
            )
    return sorted(results, key=lambda item: item.get('received', ''), reverse=True)


def get(root, record_id, kind, retention_days):
    """Read a non-expired record of the expected kind."""
    record_id = _record_id(record_id)
    if record_id is None:
        return None
    if kind == 'quarantine' and not _is_uuid(record_id):
        return None
    if kind == 'greylist' and not _MESSAGE_ID_KEY.fullmatch(record_id):
        return None
    metadata_path = root / f'{record_id}.json'
    message_path = root / f'{record_id}.eml'
    try:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        if _kind(metadata) != kind:
            return None
        if _expired(metadata_path, metadata, retention_days, kind) or not message_path.is_file():
            delete(root, record_id, kind)
            return None
        metadata['kind'] = kind
        metadata['id'] = record_id
        metadata['size'] = message_path.stat().st_size
        if kind == 'greylist':
            metadata['greylisted'] = True
        return metadata, message_path
    except (OSError, ValueError, TypeError):
        return None


def delete(root, record_id, kind=None):
    """Remove a record and its message, optionally checking its kind."""
    record_id = _record_id(record_id)
    if record_id is None:
        return False
    metadata_path = root / f'{record_id}.json'
    message_path = root / f'{record_id}.eml'
    try:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return False
    if kind and _kind(metadata) != kind:
        return False
    message_path.unlink(missing_ok=True)
    metadata_path.unlink(missing_ok=True)
    return True
