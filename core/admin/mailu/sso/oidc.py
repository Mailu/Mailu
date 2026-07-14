import base64
import hashlib
import secrets
from urllib.parse import urlencode, urljoin, urlparse, unquote

import flask
import flask_login
import requests
from flask import current_app as app
from flask_babel import lazy_gettext as _

from mailu import models


def enabled():
    return bool(app.config.get('OIDC_ENABLED'))


def redirect_uri():
    configured = app.config.get('OIDC_REDIRECT_URI')
    if configured:
        return configured
    return flask.url_for('sso.oidc_callback', _external=True)


def provider_config():
    discovery_url = app.config.get('OIDC_DISCOVERY_URL')
    if discovery_url:
        response = requests.get(discovery_url, timeout=10)
        response.raise_for_status()
        data = response.json()
    else:
        data = {}

    authorization_endpoint = app.config.get('OIDC_AUTHORIZATION_ENDPOINT') or data.get('authorization_endpoint')
    token_endpoint = app.config.get('OIDC_TOKEN_ENDPOINT') or data.get('token_endpoint')
    userinfo_endpoint = app.config.get('OIDC_USERINFO_ENDPOINT') or data.get('userinfo_endpoint')
    issuer = app.config.get('OIDC_ISSUER') or data.get('issuer')

    if not authorization_endpoint or not token_endpoint or not userinfo_endpoint:
        raise RuntimeError('OIDC is enabled but provider endpoints are incomplete')

    return {
        'authorization_endpoint': authorization_endpoint,
        'token_endpoint': token_endpoint,
        'userinfo_endpoint': userinfo_endpoint,
        'issuer': issuer,
    }


def _code_challenge(verifier):
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


def _has_usable_redirect():
    if 'homepage' in flask.request.url:
        return None
    if url := flask.request.args.get('url'):
        target = urlparse(urljoin(flask.request.url, unquote(url)))
        if target.netloc == urlparse(flask.request.url).netloc:
            return target.geturl()
    return None


def _destination():
    return _has_usable_redirect() or app.config['WEB_ADMIN']


def authorize_url():
    config = provider_config()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    flask.session['oidc_state'] = state
    flask.session['oidc_nonce'] = nonce
    flask.session['oidc_code_verifier'] = code_verifier
    flask.session['oidc_destination'] = _destination()

    query = {
        'response_type': 'code',
        'client_id': app.config['OIDC_CLIENT_ID'],
        'redirect_uri': redirect_uri(),
        'scope': app.config['OIDC_SCOPES'],
        'state': state,
        'nonce': nonce,
        'code_challenge': _code_challenge(code_verifier),
        'code_challenge_method': 'S256',
    }
    return f'{config["authorization_endpoint"]}?{urlencode(query)}'


def exchange_code(code):
    config = provider_config()
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri(),
        'client_id': app.config['OIDC_CLIENT_ID'],
        'code_verifier': flask.session.pop('oidc_code_verifier', ''),
    }
    auth = None
    headers = {'Accept': 'application/json'}
    method = app.config.get('OIDC_CLIENT_AUTH_METHOD')
    secret = app.config.get('OIDC_CLIENT_SECRET')
    if method == 'client_secret_basic' and secret:
        auth = (app.config['OIDC_CLIENT_ID'], secret)
    elif method == 'client_secret_post' and secret:
        data['client_secret'] = secret
    elif method == 'none':
        pass
    elif secret:
        auth = (app.config['OIDC_CLIENT_ID'], secret)
    response = requests.post(config['token_endpoint'], data=data, headers=headers, auth=auth, timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_userinfo(access_token):
    config = provider_config()
    response = requests.get(
        config['userinfo_endpoint'],
        headers={'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _allowed_domain(email):
    allowed = app.config.get('OIDC_ALLOWED_DOMAINS')
    if not allowed:
        return True
    domain = email.rsplit('@', 1)[1]
    return domain in allowed


def _user_from_email(email):
    user = models.User.get(email)
    if user:
        return user if user.enabled else None

    if not app.config.get('OIDC_CREATE_USER'):
        return None

    localpart, domain_name = email.rsplit('@', 1)
    domain = models.Domain.query.get(domain_name)
    if not domain:
        return None
    if domain.max_users != -1 and len(domain.users) >= domain.max_users:
        return None

    user = models.User(localpart=localpart, domain=domain)
    user.set_password(secrets.token_urlsafe(), keep_sessions=set(flask.session))
    models.db.session.add(user)
    models.db.session.commit()
    user.send_welcome()
    return user


def login_user_from_claims(claims):
    email_claim = app.config.get('OIDC_EMAIL_CLAIM') or 'email'
    email = (claims.get(email_claim) or '').strip().lower()
    if not email or '@' not in email:
        flask.current_app.logger.warning('OIDC login failed: missing email claim')
        return None

    if app.config.get('OIDC_REQUIRE_EMAIL_VERIFIED') and claims.get('email_verified') is not True:
        flask.current_app.logger.warning('OIDC login failed for %s: email is not verified', email)
        return None

    if not _allowed_domain(email):
        flask.current_app.logger.warning('OIDC login failed for %s: domain is not allowed', email)
        return None

    user = _user_from_email(email)
    if not user:
        flask.current_app.logger.warning('OIDC login failed for %s: user does not exist or cannot be created', email)
        return None

    flask.session.regenerate()
    flask_login.login_user(user)
    flask.current_app.logger.info('OIDC login succeeded for %s', email)
    return user


def validate_callback_state():
    expected = flask.session.pop('oidc_state', None)
    received = flask.request.args.get('state')
    return expected and received and secrets.compare_digest(expected, received)


def login_failed(message):
    flask.flash(message, 'error')
    return flask.redirect(flask.url_for('sso.login'))


def handle_callback():
    if error := flask.request.args.get('error'):
        description = flask.request.args.get('error_description') or error
        flask.current_app.logger.warning('OIDC provider returned an error: %s', description)
        return login_failed(_('OpenID Connect login failed'))

    if not validate_callback_state():
        flask.current_app.logger.warning('OIDC login failed: invalid state')
        return login_failed(_('OpenID Connect login failed'))

    code = flask.request.args.get('code')
    if not code:
        flask.current_app.logger.warning('OIDC login failed: missing authorization code')
        return login_failed(_('OpenID Connect login failed'))

    try:
        token = exchange_code(code)
        access_token = token.get('access_token')
        if not access_token:
            flask.current_app.logger.warning('OIDC login failed: token response omitted access_token')
            return login_failed(_('OpenID Connect login failed'))
        claims = fetch_userinfo(access_token)
        user = login_user_from_claims(claims)
    except Exception:
        flask.current_app.logger.exception('OIDC login failed')
        return login_failed(_('OpenID Connect login failed'))

    if not user:
        return login_failed(_('OpenID Connect login failed'))

    destination = flask.session.pop('oidc_destination', None) or app.config['WEB_ADMIN']
    return flask.redirect(destination)
