"""OAuth 2.0 authorization server for native mail clients.

Mailu issues opaque, short-lived access tokens and rotating refresh tokens.
Only hashes of codes and tokens are stored in the database.
"""

import base64
import hashlib
import hmac
import ipaddress
import re
import secrets
import time
from urllib.parse import urlencode, urlsplit

import flask
import flask_login
import flask_wtf
from flask import current_app as app
from flask_babel import lazy_gettext as _
from wtforms import HiddenField, SelectMultipleField, SubmitField
from wtforms.widgets import CheckboxInput

from mailu import models, signin


CLIENT_ID = 'mailu'
RESOURCE_SCOPES = {'imap', 'smtp', 'pop3', 'sieve'}
OPTIONAL_SCOPES = {'offline_access'}
ALL_SCOPES = RESOURCE_SCOPES | OPTIONAL_SCOPES
SCOPE_ORDER = ('imap', 'pop3', 'smtp', 'sieve', 'offline_access')
SCOPE_LABELS = {
    'imap': 'IMAP',
    'pop3': 'POP3',
    'smtp': 'SMTP',
    'sieve': 'SIEVE',
    'offline_access': 'offline_access',
}
SCOPE_TOOLTIPS = {
    'imap': _('Read and manage mail with IMAP'),
    'pop3': _('Retrieve mail with POP3'),
    'smtp': _('Send mail with SMTP'),
    'sieve': _('Manage server-side mail filters with Sieve'),
    'offline_access': _(
        'Allow this app to refresh access without asking you to sign in again'
    ),
}
AUTHORIZATION_CODE_TTL = 300
ACCESS_TOKEN_TTL = 24 * 3600

oauth2 = flask.Blueprint('oauth2', __name__)


class AuthorizationForm(flask_wtf.FlaskForm):
    request_id = HiddenField()
    selected_scopes = SelectMultipleField(option_widget=CheckboxInput())
    approve = SubmitField(_('Allow access'))
    deny = SubmitField(_('Cancel'))


def issuer():
    scheme = 'http' if app.config['TLS_FLAVOR'] == 'notls' else 'https'
    return f"{scheme}://{app.config['HOSTNAME']}"


def auth_url():
    return f"{issuer()}{app.config['WEB_ADMIN'].rstrip('/')}/oauth2/authorize"


def token_url():
    return f"{issuer()}{app.config['WEB_ADMIN'].rstrip('/')}/oauth2/token"


def introspection_url():
    return f"http://{app.config['ADMIN_ADDRESS']}:8080/internal/oauth2/introspect"


def _token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _scope_string(scopes):
    return ' '.join(sorted(scopes))


def _consent_scopes(scopes, user):
    ordered = [scope for scope in SCOPE_ORDER if scope in scopes]
    if not user.enable_pop:
        ordered = [scope for scope in ordered if scope != 'pop3']
    return ordered


def _valid_redirect_uri(value):
    """Accept the fixed Thunderbird localhost callback and native loopback URIs."""
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        parsed.port  # Validate the port syntax and range.
        if not host or parsed.username or parsed.password or parsed.fragment:
            return False
        if parsed.query:
            return False
        host = host.lower().rstrip('.')
        if host == 'localhost':
            return parsed.scheme in ('http', 'https')
        address = ipaddress.ip_address(host.strip('[]'))
        return address.is_loopback and parsed.scheme in ('http', 'https')
    except (ValueError, TypeError):
        return False


def _oauth_error(error, description=None, status=400):
    response = flask.jsonify(error=error, **({'error_description': description} if description else {}))
    response.status_code = status
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return response


def _redirect_with_params(uri, params):
    parsed = urlsplit(uri)
    query = '&'.join(part for part in (parsed.query, urlencode(params)) if part)
    return flask.redirect(parsed._replace(query=query).geturl(), code=302)


def _validate_authorization_request(values):
    client_id = values.get('client_id', '')
    redirect_uri = values.get('redirect_uri', '')
    if client_id != CLIENT_ID:
        return None, _oauth_error('invalid_request', 'Unknown client_id')
    if not _valid_redirect_uri(redirect_uri):
        return None, _oauth_error('invalid_request', 'Unsupported redirect_uri')
    if values.get('response_type') != 'code':
        return None, _redirect_with_params(redirect_uri, {
            'error': 'unsupported_response_type', 'state': values.get('state', ''),
        })
    if values.get('response_mode') not in (None, 'query'):
        return None, _redirect_with_params(redirect_uri, {
            'error': 'invalid_request',
            'error_description': 'Only the query response mode is supported',
            'state': values.get('state', ''),
        })

    challenge = values.get('code_challenge', '')
    method = values.get('code_challenge_method', '')
    if method != 'S256' or not 43 <= len(challenge) <= 128:
        return None, _redirect_with_params(redirect_uri, {
            'error': 'invalid_request',
            'error_description': 'PKCE with S256 is required',
            'state': values.get('state', ''),
        })
    if any(char not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for char in challenge):
        return None, _redirect_with_params(redirect_uri, {
            'error': 'invalid_request', 'state': values.get('state', ''),
        })

    requested = set(values.get('scope', '').split())
    if (
        not requested.intersection(RESOURCE_SCOPES)
        or not requested <= ALL_SCOPES
    ):
        return None, _redirect_with_params(redirect_uri, {
            'error': 'invalid_scope', 'state': values.get('state', ''),
        })
    return {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'scope': _scope_string(requested),
        'code_challenge': challenge,
        'code_challenge_method': method,
        'state': values.get('state', ''),
    }, None


@oauth2.route('/authorize', methods=['GET', 'POST'])
def authorize():
    if flask_login.current_user.is_anonymous:
        target = flask.request.full_path.rstrip('?')
        if not signin.remember(target):
            flask.abort(400)
        return flask.redirect(flask.url_for('sso.login'))
    if not flask_login.current_user.enabled:
        flask.abort(403)

    form = AuthorizationForm()
    pending = flask.session.get('oauth2_authorization_requests', {})
    if flask.request.method == 'GET':
        request_data, error = _validate_authorization_request(flask.request.args)
        if error:
            return error
        request_id = secrets.token_urlsafe(16)
        pending[request_id] = {
            **request_data,
            'user_email': flask_login.current_user.email,
        }
        # Keep concurrent consent pages supported without growing the cookie
        # indefinitely.
        while len(pending) > 5:
            pending.pop(next(iter(pending)))
        flask.session['oauth2_authorization_requests'] = pending
        form.request_id.data = request_id
        requested_scopes = _consent_scopes(request_data['scope'].split(), flask_login.current_user)
        if not set(requested_scopes).intersection(RESOURCE_SCOPES):
            pending.pop(request_id, None)
            flask.session['oauth2_authorization_requests'] = pending
            return _redirect_with_params(request_data['redirect_uri'], {
                'error': 'invalid_scope', **({'state': request_data['state']} if request_data['state'] else {}),
            })
        request_data['scope'] = _scope_string(requested_scopes)
        form.selected_scopes.choices = [
            (scope, SCOPE_LABELS[scope])
            for scope in requested_scopes
        ]
        form.selected_scopes.data = requested_scopes
    else:
        request_id = flask.request.form.get('request_id', '')
        # Older form clients (including clients with an already-open consent
        # page) may omit the new request ID. Accept this only when the session
        # has exactly one pending, CSRF-protected request.
        if not request_id and len(pending) == 1:
            request_id = next(iter(pending))
        request_data = pending.get(request_id)
        if not request_data or request_data['user_email'] != flask_login.current_user.email:
            flask.abort(400)
        form.request_id.data = request_id
        requested_scopes = _consent_scopes(request_data['scope'].split(), flask_login.current_user)
        form.selected_scopes.choices = [
            (scope, SCOPE_LABELS[scope])
            for scope in requested_scopes
        ]

    if flask.request.method == 'POST' and form.validate_on_submit():
        if form.deny.data:
            pending.pop(request_id, None)
            flask.session['oauth2_authorization_requests'] = pending
            app.logger.info(
                'OAuth authorization denied for %s (client_id=%s, scope=%s)',
                flask_login.current_user.email,
                request_data['client_id'],
                request_data['scope'],
            )
            return _redirect_with_params(request_data['redirect_uri'], {
                'error': 'access_denied', **({'state': request_data['state']} if request_data['state'] else {}),
            })

        selected_scopes = set(form.selected_scopes.data or [])
        if not selected_scopes.intersection(RESOURCE_SCOPES):
            form.selected_scopes.errors.append(_('Choose at least one mail access scope.'))
            return flask.render_template(
                'oauth2/authorize.html', form=form, scope_tooltips=SCOPE_TOOLTIPS,
            )
        request_data['scope'] = _scope_string(selected_scopes)

        user = models.db.session.get(models.User, flask_login.current_user.email)
        if not user or not user.enabled:
            pending.pop(request_id, None)
            flask.session['oauth2_authorization_requests'] = pending
            return _redirect_with_params(request_data['redirect_uri'], {
                'error': 'access_denied', **({'state': request_data['state']} if request_data['state'] else {}),
            })

        raw_code = secrets.token_urlsafe(32)
        models.db.session.add(models.OAuth2AuthorizationCode(
            code_hash=_token_hash(raw_code),
            user=user,
            client_id=request_data['client_id'],
            redirect_uri=request_data['redirect_uri'],
            scope=request_data['scope'],
            code_challenge=request_data['code_challenge'],
            expires_at=int(time.time()) + AUTHORIZATION_CODE_TTL,
        ))
        models.db.session.commit()
        pending.pop(request_id, None)
        flask.session['oauth2_authorization_requests'] = pending
        app.logger.info(
            'OAuth authorization approved for %s (client_id=%s, scope=%s)',
            user.email,
            request_data['client_id'],
            request_data['scope'],
        )
        return _redirect_with_params(request_data['redirect_uri'], {
            'code': raw_code,
            **({'state': request_data['state']} if request_data['state'] else {}),
        })

    return flask.render_template(
        'oauth2/authorize.html', form=form, scope_tooltips=SCOPE_TOOLTIPS,
    )


def _issue_tokens(user_email, client_id, scope, grant=None):
    now = int(time.time())
    access_token = secrets.token_urlsafe(32)
    has_offline_access = 'offline_access' in scope.split()
    refresh_token = secrets.token_urlsafe(48) if has_offline_access else None
    is_refresh = grant is not None
    if grant is None:
        grant = models.OAuth2Grant(
            user_email=user_email,
            client_id=client_id,
            scope=scope,
            client_name=_client_name(),
        )
        models.db.session.add(grant)
        grant.last_refresh_at = now
        grant.refresh_expires_at = (
            now + app.config['OAUTH2_REFRESH_TOKEN_TTL'] if refresh_token else None
        )
    else:
        if grant.refresh_token_hash:
            models.db.session.add(models.OAuth2RefreshTokenHistory(
                token_hash=grant.refresh_token_hash,
                grant_id=grant.id,
                used_at=now,
            ))
        grant.client_name = _client_name()
        grant.last_refresh_at = now
    grant.access_token_hash = _token_hash(access_token)
    grant.refresh_token_hash = _token_hash(refresh_token) if refresh_token else None
    grant.scope = scope
    grant.access_expires_at = now + ACCESS_TOKEN_TTL
    models.db.session.commit()
    app.logger.info(
        'OAuth tokens %s for %s (client_id=%s, scope=%s, access_ttl=%ds, refresh_ttl=%s, refresh_idle=%s)',
        'refreshed and rotated' if is_refresh else 'issued',
        user_email,
        client_id,
        scope,
        ACCESS_TOKEN_TTL,
        f"{app.config['OAUTH2_REFRESH_TOKEN_TTL']}s" if refresh_token else 'disabled',
        f"{app.config['OAUTH2_REFRESH_TOKEN_IDLE']}s" if refresh_token else 'disabled',
    )
    response = {
        'access_token': access_token,
        'token_type': 'Bearer',
        'expires_in': ACCESS_TOKEN_TTL,
        'scope': scope,
    }
    if refresh_token:
        response['refresh_token'] = refresh_token
    return response


def _client_name():
    """Return a short, displayable name for the MUA from its User-Agent."""
    user_agent = flask.request.user_agent.string
    thunderbird = re.search(r'Thunderbird/([A-Za-z0-9.+_-]+)', user_agent, re.IGNORECASE)
    if thunderbird:
        return f'Thunderbird {thunderbird.group(1)}'[:120]
    product = re.search(r'([A-Za-z][A-Za-z0-9 ._-]{0,50})/([A-Za-z0-9.+_-]+)', user_agent)
    if product:
        return f'{product.group(1).strip()} {product.group(2)}'[:120]
    return 'Mail app'


@oauth2.post('/token')
def token():
    data = flask.request.form
    if data.get('client_id') != CLIENT_ID:
        return _oauth_error('invalid_client')

    now = int(time.time())
    grant_type = data.get('grant_type')
    if grant_type == 'authorization_code':
        raw_code = data.get('code', '')
        record = models.OAuth2AuthorizationCode.query.filter_by(
            code_hash=_token_hash(raw_code), client_id=CLIENT_ID,
        ).with_for_update().first()
        verifier = data.get('code_verifier', '')
        try:
            valid_verifier = (
                43 <= len(verifier) <= 128
                and all(char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~' for char in verifier)
            )
            calculated = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest())
                .rstrip(b'=').decode('ascii')
                if valid_verifier else ''
            )
        except (UnicodeEncodeError, AttributeError):
            calculated = ''
        valid = bool(
            record and record.expires_at > now
            and record.redirect_uri == data.get('redirect_uri')
            and hmac.compare_digest(calculated, record.code_challenge)
        )
        if not valid:
            models.db.session.rollback()
            return _oauth_error('invalid_grant')
        user = models.db.session.get(models.User, record.user_email)
        if not user or not user.enabled:
            models.db.session.delete(record)
            models.db.session.commit()
            return _oauth_error('invalid_grant')
        models.db.session.delete(record)
        try:
            response = _issue_tokens(user.email, CLIENT_ID, record.scope)
        except Exception:
            models.db.session.rollback()
            raise
        return _token_response(response)

    if grant_type == 'refresh_token':
        raw_refresh = data.get('refresh_token', '')
        refresh_hash = _token_hash(raw_refresh)
        grant = models.OAuth2Grant.query.filter_by(
            refresh_token_hash=refresh_hash, client_id=CLIENT_ID,
        ).with_for_update().first()
        if not grant:
            used_token = models.OAuth2RefreshTokenHistory.query.filter_by(
                token_hash=refresh_hash,
            ).with_for_update().first()
            if used_token:
                replayed_grant = models.OAuth2Grant.query.filter_by(
                    id=used_token.grant_id, client_id=CLIENT_ID,
                ).with_for_update().first()
                if replayed_grant:
                    app.logger.warning(
                        'OAuth refresh token replay detected for %s '
                        '(client_id=%s, scope=%s); revoking grant family',
                        replayed_grant.user_email, replayed_grant.client_id, replayed_grant.scope,
                    )
                    models.db.session.delete(replayed_grant)
                    models.db.session.commit()
                else:
                    models.db.session.rollback()
            else:
                models.db.session.rollback()
            return _oauth_error('invalid_grant')

        last_use = grant.last_refresh_at
        if last_use is None and grant.refresh_expires_at is not None:
            # Old grants without activity timestamps were issued with this
            # absolute expiry calculated from their issuance time.
            last_use = grant.refresh_expires_at - app.config['OAUTH2_REFRESH_TOKEN_TTL']
        if (
            grant.refresh_expires_at is None
            or grant.refresh_expires_at <= now
            or last_use is None
            or last_use + app.config['OAUTH2_REFRESH_TOKEN_IDLE'] <= now
        ):
            models.db.session.delete(grant)
            models.db.session.commit()
            return _oauth_error('invalid_grant')
        user = models.db.session.get(models.User, grant.user_email)
        if not user or not user.enabled:
            models.db.session.delete(grant)
            models.db.session.commit()
            return _oauth_error('invalid_grant')
        response = _issue_tokens(user.email, CLIENT_ID, grant.scope, grant=grant)
        return _token_response(response)

    return _oauth_error('unsupported_grant_type')


def _token_response(values):
    response = flask.jsonify(values)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return response


@oauth2.post('/revoke')
def revoke():
    data = flask.request.form
    if data.get('client_id') != CLIENT_ID:
        return _oauth_error('invalid_client')
    token_hash = _token_hash(data.get('token', ''))
    grant = models.OAuth2Grant.query.filter(
        (models.OAuth2Grant.access_token_hash == token_hash)
        | (models.OAuth2Grant.refresh_token_hash == token_hash)
    ).first()
    if grant:
        user_email = grant.user_email
        client_id = grant.client_id
        scope = grant.scope
        models.db.session.delete(grant)
        models.db.session.commit()
        app.logger.info(
            'OAuth grant revoked for %s (client_id=%s, scope=%s)',
            user_email, client_id, scope,
        )
    response = flask.Response(status=200)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return response


def server_metadata():
    response = flask.jsonify({
        'issuer': issuer(),
        'authorization_endpoint': auth_url(),
        'token_endpoint': token_url(),
        'revocation_endpoint': f"{issuer()}{app.config['WEB_ADMIN'].rstrip('/')}/oauth2/revoke",
        'response_types_supported': ['code'],
        'response_modes_supported': ['query'],
        'grant_types_supported': ['authorization_code', 'refresh_token'],
        'code_challenge_methods_supported': ['S256'],
        'token_endpoint_auth_methods_supported': ['none'],
        'revocation_endpoint_auth_methods_supported': ['none'],
        'scopes_supported': sorted(ALL_SCOPES),
    })
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response
