"""OAuth token introspection for Dovecot's private network request."""

import time

import flask

from mailu import models
from mailu.internal import internal
from mailu.oauth2 import issuer, _parse_mail_token


@internal.post('/oauth2/introspect')
def oauth2_introspect():
    raw_token = flask.request.form.get('token', '')
    if not raw_token:
        return flask.jsonify(active=False)

    now = int(time.time())
    parsed = _parse_mail_token(raw_token, 'access')
    grant = models.OAuth2Grant.query.with_entities(
        models.OAuth2Grant.user_email, models.OAuth2Grant.token_generation,
        models.OAuth2Grant.access_expires_at, models.OAuth2Grant.client_id,
        models.OAuth2Grant.scope,
    ).filter_by(grant_id=parsed[1]).first() if parsed else None
    user = models.User.query.with_entities(
        models.User.email, models.User.enabled, models.User.enable_imap,
        models.User.enable_pop,
    ).filter_by(_email=grant.user_email).first() if grant else None
    protocol = flask.request.headers.get('X-Dovecot-Auth-Protocol')
    protocol_scopes = {
        'imap': 'imap',
        'smtp': 'smtp',
        'submission': 'smtp',
        'pop3': 'pop3',
        'sieve': 'sieve',
    }
    protocol_ports = {
        'imap': 143,
        'smtp': 10025,
        'submission': 2587,
        'pop3': 110,
        'sieve': 4190,
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
        not grant or parsed[2] != grant.token_generation
        or grant.access_expires_at <= now or not user or not user.enabled
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
        'port': protocol_ports.get(protocol, 143),
    })
