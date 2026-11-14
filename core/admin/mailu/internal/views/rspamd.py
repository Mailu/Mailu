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
    domain_name_row = models.Domain.query.with_entities(models.Domain.name).filter_by(name=domain_name).first()
    alternative = models.Alternative.query.with_entities(
        models.Alternative.domain_name,
    ).filter_by(name=domain_name).first()
    signing_domains = {domain_name_row[0]} if domain_name_row else set()
    if alternative:
        signing_domains.add(alternative[0])
    seen = set()
    keys = models.DkimKey.query.with_entities(
        models.DkimKey.selector, models.DkimKey.private_key, models.DkimKey.algorithm,
    ).filter(
        models.DkimKey.domain_name.in_(signing_domains),
        models.DkimKey.active.is_(True),
    ).all() if signing_domains else []
    for selector, private_key, algorithm in keys:
        if selector not in seen:
            seen.add(selector)
            selectors.append({
                'domain': idna.encode(domain_name.lower()).decode('ascii'),
                'key': private_key.decode('utf8'),
                'selector': selector,
                'alg': algorithm,
            })
    return flask.jsonify({'data': {'selectors': selectors}})

@internal.route("/rspamd/local_domains", methods=['GET'])
def rspamd_local_domains():
    domains = {domain[0] for domain in models.Domain.query.with_entities(models.Domain.name).all()}
    domains.update(domain[0] for domain in
                   models.Alternative.query.with_entities(models.Alternative.name).all())
    content = '\n'.join(sorted(domains, key=str.casefold))
    return rspamd_map_response(content)


def rspamd_map_response(content):
    """Serve an Rspamd map with cache validation headers."""
    response = flask.Response(content, mimetype='text/plain; charset=utf-8')
    response.headers['Cache-Control'] = 'public, max-age=30'
    response.set_etag(hashlib.sha256(content.encode('utf-8')).hexdigest())
    return response.make_conditional(flask.request)


@internal.route('/rspamd/spam-map/<map_name>', methods=['GET'])
def rspamd_spam_map(map_name):
    content = spam_settings.map_content(map_name)
    if content is None:
        flask.abort(404)
    return rspamd_map_response(content)


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
        mailbox_recipients.update(
            mailbox.email.lower() for mailbox in models.Email.resolve_mailboxes(address)
        )
    metadata['rcpt'] = sorted(mailbox_recipients or envelope_recipients)
    try:
        result = greylist.record(metadata, raw_message)
    except (OSError, ValueError):
        flask.current_app.logger.exception('Could not persist greylisted message')
        flask.abort(503)
    if result is None:
        flask.abort(400)
    return flask.jsonify({'recorded': result}), 200
