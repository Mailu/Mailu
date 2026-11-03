import hmac
import json
from datetime import datetime, timezone

import flask
from flask import current_app as app

from mailu import models, quarantine
from mailu.internal import internal


@internal.route('/rspamd/quarantine', methods=['POST'])
def rspamd_quarantine():
    if flask.request.content_length and flask.request.content_length > app.config['QUARANTINE_MAX_MESSAGE_BYTES'] + 1048576:
        flask.abort(413)
    credentials = flask.request.authorization
    if (not credentials or credentials.username != 'quarantine'
            or not hmac.compare_digest(credentials.password or '', app.config['QUARANTINE_KEY'])):
        flask.abort(403)
    if not flask.request.mimetype.startswith('multipart/'):
        flask.abort(415)
    try:
        metadata_part = flask.request.form.get('metadata')
        if metadata_part is None and 'metadata' in flask.request.files:
            metadata_part = flask.request.files['metadata'].stream.read(1048576)
        metadata = json.loads(metadata_part)
        message = flask.request.files['message'].stream.read(app.config['QUARANTINE_MAX_MESSAGE_BYTES'] + 1)
    except (KeyError, ValueError, TypeError):
        flask.abort(400)
    if len(message) > app.config['QUARANTINE_MAX_MESSAGE_BYTES']:
        flask.abort(413)
    if not isinstance(metadata, dict):
        flask.abort(400)
    if metadata.get('action') != 'reject':
        flask.abort(400)
    recipients = metadata.get('rcpt', metadata.get('recipients', []))
    if isinstance(recipients, str):
        recipients = [recipients]
    if not isinstance(recipients, list):
        flask.abort(400)
    envelope_recipients = sorted({item.strip().lower() for item in recipients if isinstance(item, str) and '@' in item})
    metadata['envelope_recipients'] = envelope_recipients
    mailbox_recipients = set()
    for address in envelope_recipients:
        localpart, domain = models.User.resolve_domain(address)
        for destination in models.User.resolve_destination(localpart, domain) or []:
            mailbox = models.User.get(destination.lower())
            if mailbox:
                mailbox_recipients.add(mailbox.email.lower())
    metadata['recipients'] = sorted(mailbox_recipients or envelope_recipients)
    metadata['symbols'] = metadata.get('symbols') if isinstance(metadata.get('symbols'), list) else []
    metadata['received'] = datetime.now(timezone.utc).isoformat()
    try:
        message_id = quarantine.store(message, metadata)
    except ValueError:
        flask.abort(413)
    except OSError:
        app.logger.exception('Could not persist quarantined message')
        flask.abort(503)
    return flask.jsonify({'id': message_id}), 201
