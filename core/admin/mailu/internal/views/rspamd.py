import hashlib
import hmac
import json

from mailu import greylist, models, spam_settings
from mailu.internal import internal

import flask
import idna

def vault_error(*messages, status=404):
    return flask.make_response(flask.jsonify({'errors':messages}), status)

# rspamd key format:
# {"selectors":[{"pubkey":"...","domain":"...","valid_start":TS,"valid_end":TS,"key":"...","selector":"...","bits":...,"alg":"..."}]}

# hashicorp vault answer format:
# {"request_id":"...","lease_id":"","renewable":false,"lease_duration":2764800,"data":{...see above...},"wrap_info":null,"warnings":null,"auth":null}

@internal.route("/rspamd/vault/v1/dkim/<domain_name>", methods=['GET'])
def rspamd_dkim_key(domain_name):
    selectors = []
    domain = models.db.session.get(models.Domain, domain_name)
    alternative = models.db.session.get(models.Alternative, domain_name)
    signing_domains = [item for item in (domain, alternative.domain if alternative else None) if item]
    seen = set()
    for signing_domain in signing_domains:
        for key in signing_domain.dkim_keys:
            if key.active and key.selector not in seen:
                seen.add(key.selector)
                selectors.append({
                    'domain': idna.encode(domain_name.lower()).decode('ascii'),
                    'key': key.private_key.decode('utf8'),
                    'selector': key.selector,
                    'alg': key.algorithm,
                })
    return flask.jsonify({'data': {'selectors': selectors}})

@internal.route("/rspamd/local_domains", methods=['GET'])
def rspamd_local_domains():
    return '\n'.join(domain[0] for domain in models.Domain.query.with_entities(models.Domain.name).all() + models.Alternative.query.with_entities(models.Alternative.name).all())


@internal.route('/rspamd/spam-map/<map_name>', methods=['GET'])
def rspamd_spam_map(map_name):
    content = spam_settings.map_content(map_name)
    if content is None:
        flask.abort(404)
    response = flask.Response(content, mimetype='text/plain; charset=utf-8')
    response.headers['Cache-Control'] = 'public, max-age=30'
    response.set_etag(hashlib.sha256(content.encode('utf-8')).hexdigest())
    return response


@internal.route('/rspamd/greylist', methods=['POST'])
def rspamd_greylist():
    maximum = flask.current_app.config['QUARANTINE_MAX_MESSAGE_BYTES']
    if flask.request.content_length and flask.request.content_length > maximum + 1048576:
        flask.abort(413)
    credentials = flask.request.authorization
    if (not credentials or credentials.username != 'quarantine'
            or not hmac.compare_digest(credentials.password or '', flask.current_app.config['QUARANTINE_KEY'])):
        flask.abort(403)
    if flask.request.mimetype == 'multipart/form-data':
        try:
            metadata_part = flask.request.form.get('metadata')
            if metadata_part is None and 'metadata' in flask.request.files:
                metadata_part = flask.request.files['metadata'].stream.read(1048576).decode('utf-8')
            metadata = json.loads(metadata_part)
            raw_message = flask.request.files['message'].stream.read(maximum + 1)
        except (KeyError, ValueError, TypeError, UnicodeDecodeError):
            flask.abort(400)
        if len(raw_message) > maximum:
            flask.abort(413)
    elif flask.request.is_json:
        try:
            metadata = flask.request.get_json()
        except (ValueError, TypeError):
            flask.abort(400)
        raw_message = None
    else:
        flask.abort(415)
    if not isinstance(metadata, dict):
        flask.abort(400)

    if raw_message is None:
        # Accepted message callbacks contain only the small metadata needed to
        # remove a previously saved greylist retry. Avoid resolving recipients
        # or persisting this ordinary delivery callback.
        result = greylist.record(metadata)
        if result is None:
            flask.abort(400)
        return flask.jsonify({'recorded': result}), 200

    recipients = metadata.get('rcpt', metadata.get('recipients', []))
    if isinstance(recipients, str):
        recipients = [recipients]
    if not isinstance(recipients, list):
        flask.abort(400)
    envelope_recipients = sorted({item.strip().lower() for item in recipients
                                  if isinstance(item, str) and '@' in item and len(item) <= 320})
    metadata['envelope_recipients'] = envelope_recipients
    mailbox_recipients = set()
    for address in envelope_recipients:
        localpart, domain = models.User.resolve_domain(address)
        for destination in models.User.resolve_destination(localpart, domain) or []:
            mailbox = models.User.get(destination.lower())
            if mailbox:
                mailbox_recipients.add(mailbox.email.lower())
    metadata['rcpt'] = sorted(mailbox_recipients or envelope_recipients)
    try:
        result = greylist.record(metadata, raw_message)
    except (OSError, ValueError):
        flask.current_app.logger.exception('Could not persist greylisted message')
        flask.abort(503)
    if result is None:
        flask.abort(400)
    return flask.jsonify({'recorded': result}), 200
