"""OAuth token introspection for Dovecot's private network request."""

import time

import flask

from mailu import models
from mailu.internal import internal
from mailu.oauth2 import issuer, _token_hash


@internal.post('/oauth2/introspect')
def oauth2_introspect():
    raw_token = flask.request.form.get('token', '')
    if not raw_token:
        return flask.jsonify(active=False)

    now = int(time.time())
    grant = models.OAuth2Grant.query.filter_by(
        access_token_hash=_token_hash(raw_token),
    ).first()
    user = models.db.session.get(models.User, grant.user_email) if grant else None
    protocol = flask.request.headers.get('X-Dovecot-Auth-Protocol')
    protocol_scopes = {
        'imap': 'imap',
        'smtp': 'smtp',
        'submission': 'smtp',
        'pop3': 'pop3',
        'sieve': 'sieve',
    }
    required_scope = protocol_scopes.get(protocol) if protocol else None
    protocol_enabled = (
        protocol is None or (grant and
            required_scope in grant.scope.split()
            and not (protocol == 'imap' and user and not user.enable_imap)
            and not (protocol == 'pop3' and user and not user.enable_pop)
        )
    )
    if (
        not grant or grant.access_expires_at <= now or not user or not user.enabled
        or not protocol_enabled
    ):
        return flask.jsonify(active=False)

    return flask.jsonify({
        'active': True,
        'iss': issuer(),
        'sub': user.email,
        'email': user.email,
        'username': user.email,
        'client_id': grant.client_id,
        'scope': grant.scope,
        'token_type': 'Bearer',
        'exp': grant.access_expires_at,
    })
