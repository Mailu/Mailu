"""Keycloak (OpenID Connect) sign-in with enforced multi-factor authentication.

Mailu acts as an OIDC relying party using the authorization code flow with
PKCE, a nonce and a state value. The ID token is verified against the realm's
published signing keys, and the sign-in is rejected unless Keycloak reports a
multi-factor authentication through the ``acr`` or ``amr`` claim.

Two-factor authentication is required per mailbox: the mailbox setting wins,
then the domain setting, then ``KEYCLOAK_MFA_DEFAULT``. For a mailbox that
requires it, Keycloak is the only way to start a web session, and the mailbox
password stops working for IMAP, POP3, SMTP, Sieve and DAV. Mail clients then
authenticate with Mailu's OAuth 2.0 tokens (whose consent page sits behind the
Keycloak sign-in) or with app tokens created after signing in with Keycloak.
"""

import base64
import hashlib
import secrets
import threading
import time
from urllib.parse import urlencode, urlsplit

import flask
import jwt
import requests
import sqlalchemy.exc
from flask import current_app as app
from flask_babel import lazy_gettext as _

from mailu import models
from mailu.oauth2 import issuer


SESSION_AUTH_METHOD = 'auth_method'
SESSION_PENDING = 'keycloak_pending'
SESSION_ID_TOKEN = 'keycloak_id_token'
# Session authentication methods that satisfy a 2FA requirement. Header
# authentication from a whitelisted proxy remains an explicit operator choice.
TRUSTED_AUTH_METHODS = {'keycloak', 'proxy'}

PENDING_TTL = 600
MAX_PENDING = 5
METADATA_TTL = 3600
JWKS_MIN_REFRESH = 60
HTTP_TIMEOUT = 10
CLOCK_SKEW = 60
ALLOWED_ALGORITHMS = {
    'RS256', 'RS384', 'RS512', 'PS256', 'PS384', 'PS512', 'ES256', 'ES384', 'ES512', 'EdDSA',
}

_lock = threading.Lock()

NO_SECOND_FACTOR = _(
    'Your sign-in did not use two-factor authentication. '
    'Set up a second factor in your account and try again.'
)


class KeycloakError(Exception):
    """A sign-in failure. ``reason`` is logged; ``message`` is safe to show."""

    def __init__(self, reason, message=None):
        super().__init__(reason)
        self.reason = reason
        self.message = message


def enabled():
    return bool(app.config.get('KEYCLOAK_ISSUER'))


def _lookup(model, key):
    try:
        return models.db.session.get(model, key)
    except sqlalchemy.exc.StatementError:
        return None


def mfa_required_for(user=None, email=None):
    """Return whether a mailbox must sign in through Keycloak with 2FA.

    ``email`` may name a mailbox that does not exist; the domain setting and
    then the default apply, so the answer does not reveal which mailboxes
    exist within a domain.
    """
    if not enabled():
        return False
    if user is None and isinstance(email, str) and '@' in email:
        email = email.strip().lower()
        user = _lookup(models.User, email)
        domain = None if user is not None else _lookup(models.Domain, email.rsplit('@', 1)[1])
    else:
        domain = None
    if user is not None:
        if user.mfa_required is not None:
            return user.mfa_required
        domain = user.domain
    if domain is not None and domain.mfa_required is not None:
        return domain.mfa_required
    return bool(app.config.get('KEYCLOAK_MFA_DEFAULT'))


def mfa_exemptions_exist():
    """Return whether any domain or mailbox may sign in without Keycloak."""
    if not enabled():
        return True
    if not app.config.get('KEYCLOAK_MFA_DEFAULT'):
        return True
    return bool(
        models.db.session.query(models.Domain.name)
        .filter(models.Domain.mfa_required.is_(False)).first()
        or models.db.session.query(models.User.email)
        .filter(models.User.mfa_required.is_(False)).first()
    )


def session_is_trusted(session):
    return session.get(SESSION_AUTH_METHOD) in TRUSTED_AUTH_METHODS


def load_user(user_id):
    """Flask-Login loader that ignores sessions Keycloak did not create.

    Without this, sessions opened with a password before 2FA was required for
    the mailbox would keep working until they expire.
    """
    user = models.User.get(user_id)
    if user is not None and not session_is_trusted(flask.session) and mfa_required_for(user):
        return None
    return user


def _split(value):
    return [item.strip() for item in str(value or '').split(',') if item.strip()]


def required_acr():
    return _split(app.config.get('KEYCLOAK_REQUIRED_ACR'))


def required_amr():
    return _split(app.config.get('KEYCLOAK_REQUIRED_AMR'))


def _issuer():
    return app.config['KEYCLOAK_ISSUER'].rstrip('/')


def _cache():
    if not hasattr(app, 'keycloak_cache'):
        app.keycloak_cache = {}
    return app.keycloak_cache


def _http_get(url):
    response = requests.get(url, timeout=HTTP_TIMEOUT, headers={'Accept': 'application/json'})
    response.raise_for_status()
    return response.json()


def _http_post(url, data):
    response = requests.post(
        url, data=data, timeout=HTTP_TIMEOUT, headers={'Accept': 'application/json'},
    )
    try:
        body = response.json()
    except ValueError:
        body = {}
    return response.status_code, body


def metadata():
    """Return the realm's OpenID provider metadata, cached for an hour."""
    cache = _cache()
    cached = cache.get('metadata')
    if cached and cached[0] > time.time():
        return cached[1]
    url = f'{_issuer()}/.well-known/openid-configuration'
    try:
        document = _http_get(url)
    except (requests.RequestException, ValueError) as exc:
        raise KeycloakError(f'cannot load provider metadata from {url}: {exc}') from exc
    if not isinstance(document, dict) or document.get('issuer', '').rstrip('/') != _issuer():
        found = document.get('issuer') if isinstance(document, dict) else None
        raise KeycloakError(
            f'provider metadata issuer {found!r} '
            f'does not match KEYCLOAK_ISSUER {_issuer()!r}'
        )
    for field in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
        if not isinstance(document.get(field), str) or not document[field]:
            raise KeycloakError(f'provider metadata lacks {field}')
    with _lock:
        cache['metadata'] = (time.time() + METADATA_TTL, document)
    return document


def _signing_key(kid):
    """Return the realm key for ``kid``, refreshing the JWKS on rotation."""
    cache = _cache()
    jwks = cache.get('jwks')
    if jwks and kid in jwks[1]:
        return jwks[1][kid]
    if jwks and jwks[0] + JWKS_MIN_REFRESH > time.time():
        raise KeycloakError(f'unknown ID token signing key {kid!r}')
    try:
        document = _http_get(metadata()['jwks_uri'])
    except (requests.RequestException, ValueError) as exc:
        raise KeycloakError(f'cannot load signing keys: {exc}') from exc
    keys = {}
    for entry in document.get('keys', []) if isinstance(document, dict) else []:
        if entry.get('use', 'sig') != 'sig' or not entry.get('kid'):
            continue
        try:
            keys[entry['kid']] = (jwt.PyJWK(entry), entry.get('alg'))
        except (jwt.PyJWKError, jwt.InvalidKeyError):
            # Keycloak also publishes encryption keys and algorithms that
            # PyJWT may not support; only signing keys matter here.
            continue
    with _lock:
        cache['jwks'] = (time.time(), keys)
    if kid not in keys:
        raise KeycloakError(f'unknown ID token signing key {kid!r}')
    return keys[kid]


def redirect_uri():
    return f"{issuer()}{flask.url_for('sso.keycloak_callback')}"


def post_logout_redirect_uri():
    return f"{issuer()}{flask.url_for('sso.login')}"


def authorization_redirect(login_hint=None):
    """Remember a new pending sign-in and return the Keycloak redirect URL."""
    provider = metadata()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode('ascii')).digest()
    ).rstrip(b'=').decode('ascii')
    callback = redirect_uri()
    pending = dict(flask.session.get(SESSION_PENDING, {}))
    now = time.time()
    pending = {key: value for key, value in pending.items() if value.get('expires', 0) > now}
    pending[state] = {
        'nonce': nonce,
        'verifier': verifier,
        'redirect_uri': callback,
        'expires': now + PENDING_TTL,
    }
    while len(pending) > MAX_PENDING:
        pending.pop(next(iter(pending)))
    flask.session[SESSION_PENDING] = pending

    params = {
        'client_id': app.config['KEYCLOAK_CLIENT_ID'],
        'response_type': 'code',
        'scope': app.config['KEYCLOAK_SCOPES'],
        'redirect_uri': callback,
        'state': state,
        'nonce': nonce,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    }
    if login_hint:
        params['login_hint'] = login_hint
    if acr := required_acr():
        # Keycloak maps these values to a level of authentication through
        # the client's "ACR to LoA mapping" and runs the matching step-up.
        params['acr_values'] = ' '.join(acr)
    endpoint = provider['authorization_endpoint']
    return f"{endpoint}{'&' if urlsplit(endpoint).query else '?'}{urlencode(params)}"


def take_pending(state):
    """Remove and return the pending sign-in for ``state``, if still valid."""
    pending = dict(flask.session.get(SESSION_PENDING, {}))
    entry = pending.pop(state, None) if isinstance(state, str) and state else None
    if pending:
        flask.session[SESSION_PENDING] = pending
    else:
        flask.session.pop(SESSION_PENDING, None)
    if not entry or entry.get('expires', 0) <= time.time():
        return None
    return entry


def exchange_code(code, pending):
    """Redeem an authorization code and return the verified ID token claims."""
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': pending['redirect_uri'],
        'client_id': app.config['KEYCLOAK_CLIENT_ID'],
        'code_verifier': pending['verifier'],
    }
    if app.config.get('KEYCLOAK_CLIENT_SECRET'):
        data['client_secret'] = app.config['KEYCLOAK_CLIENT_SECRET']
    try:
        status, body = _http_post(metadata()['token_endpoint'], data)
    except requests.RequestException as exc:
        raise KeycloakError(f'token request failed: {exc}') from exc
    if status != 200 or not isinstance(body.get('id_token'), str):
        raise KeycloakError(
            f'token endpoint returned HTTP {status}: '
            f'{body.get("error")!r} {body.get("error_description")!r}'
        )
    claims = verify_id_token(body['id_token'], pending['nonce'])
    return claims, body['id_token']


def verify_id_token(token, nonce):
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise KeycloakError(f'malformed ID token: {exc}') from exc
    algorithm = header.get('alg')
    if algorithm not in ALLOWED_ALGORITHMS:
        raise KeycloakError(f'ID token uses disallowed algorithm {algorithm!r}')
    key, key_algorithm = _signing_key(header.get('kid'))
    if key_algorithm and key_algorithm != algorithm:
        raise KeycloakError(f'ID token algorithm {algorithm!r} does not match its key')
    client_id = app.config['KEYCLOAK_CLIENT_ID']
    try:
        claims = jwt.decode(
            token, key=key.key, algorithms=[algorithm], audience=client_id,
            issuer=_issuer(), leeway=CLOCK_SKEW,
            options={'require': ['exp', 'iat', 'iss', 'aud', 'sub']},
        )
    except jwt.InvalidTokenError as exc:
        raise KeycloakError(f'invalid ID token: {exc}') from exc
    presented_nonce = claims.get('nonce')
    if not isinstance(presented_nonce, str) or not secrets.compare_digest(presented_nonce, nonce):
        raise KeycloakError('ID token nonce does not match')
    audiences = claims['aud'] if isinstance(claims['aud'], list) else [claims['aud']]
    if len(audiences) > 1 and claims.get('azp') != client_id:
        raise KeycloakError('ID token has several audiences but azp is not this client')
    if 'azp' in claims and claims['azp'] != client_id:
        raise KeycloakError(f'ID token was issued to {claims["azp"]!r}')
    return claims


def check_mfa(claims):
    """Reject sign-ins for which Keycloak does not assert a second factor."""
    acr = required_acr()
    amr = required_amr()
    if acr and str(claims.get('acr', '')) not in acr:
        raise KeycloakError(
            f'acr {claims.get("acr")!r} is not one of KEYCLOAK_REQUIRED_ACR {acr}',
            NO_SECOND_FACTOR,
        )
    if amr:
        presented = claims.get('amr') or []
        if isinstance(presented, str):
            presented = [presented]
        if not set(amr).intersection(presented):
            raise KeycloakError(
                f'amr {presented!r} contains none of KEYCLOAK_REQUIRED_AMR {amr}',
                NO_SECOND_FACTOR,
            )


def email_from_claims(claims):
    claim = app.config['KEYCLOAK_EMAIL_CLAIM']
    email = claims.get(claim)
    if not isinstance(email, str) or '@' not in email:
        raise KeycloakError(
            f'ID token claim {claim!r} is missing or not an e-mail address',
            _('Your single sign-on account has no e-mail address.'),
        )
    if (claim == 'email' and app.config['KEYCLOAK_REQUIRE_VERIFIED_EMAIL']
            and claims.get('email_verified') is not True):
        raise KeycloakError(
            f'e-mail address {email!r} is not verified in Keycloak',
            _('Your e-mail address is not verified in your single sign-on account.'),
        )
    return email.strip().lower()


def find_or_create_user(email):
    """Return the Mailu user for a Keycloak identity, creating one if allowed."""
    try:
        user = models.User.get(email)
    except sqlalchemy.exc.StatementError:
        user = None
    if user is not None:
        if not user.enabled:
            raise KeycloakError(f'mailbox {email} is disabled', _('This mailbox is disabled.'))
        return user
    no_mailbox = _('There is no mailbox for your account on this server.')
    if not app.config['KEYCLOAK_CREATE_USERS']:
        raise KeycloakError(f'no mailbox for {email} and KEYCLOAK_CREATE_USERS is off', no_mailbox)
    localpart, domain_name = email.rsplit('@', 1)
    try:
        domain = models.db.session.get(models.Domain, domain_name)
    except sqlalchemy.exc.StatementError:
        domain = None
    if domain is None:
        raise KeycloakError(f'cannot create {email}: domain is not hosted here', no_mailbox)
    if domain.max_users != -1 and len(domain.users) >= domain.max_users:
        raise KeycloakError(f'cannot create {email}: domain {domain} is full', no_mailbox)
    user = models.User(localpart=localpart, domain=domain)
    # The password is never revealed, and is refused while 2FA is required.
    user.set_password(secrets.token_urlsafe(32), keep_sessions=True)
    models.db.session.add(user)
    models.db.session.commit()
    user.send_welcome()
    app.logger.info(f'Created mailbox {email} for a new Keycloak user')
    return user


def end_session_url(id_token):
    """Return Keycloak's RP-initiated logout URL, or None when unavailable."""
    try:
        endpoint = metadata().get('end_session_endpoint')
    except KeycloakError as exc:
        app.logger.warning(f'Keycloak logout skipped: {exc.reason}')
        return None
    if not endpoint:
        return None
    params = {
        'client_id': app.config['KEYCLOAK_CLIENT_ID'],
        'post_logout_redirect_uri': post_logout_redirect_uri(),
    }
    if id_token:
        params['id_token_hint'] = id_token
    return f"{endpoint}{'&' if urlsplit(endpoint).query else '?'}{urlencode(params)}"
