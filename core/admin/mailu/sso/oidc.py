import base64
import hashlib
import json
import secrets
import time
from urllib.parse import urlencode, urljoin, urlparse, unquote

import flask
import flask_login
import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.hashes import SHA256, SHA384, SHA512
from flask import current_app as app
from flask_babel import lazy_gettext as _

from mailu import models


JWT_ALGORITHMS = {
    'RS256': (padding.PKCS1v15(), SHA256()),
    'RS384': (padding.PKCS1v15(), SHA384()),
    'RS512': (padding.PKCS1v15(), SHA512()),
}


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
    jwks_uri = app.config.get('OIDC_JWKS_URI') or data.get('jwks_uri')
    issuer = app.config.get('OIDC_ISSUER') or data.get('issuer')

    if not authorization_endpoint or not token_endpoint or not userinfo_endpoint or not jwks_uri:
        raise RuntimeError('OIDC is enabled but provider endpoints are incomplete')

    return {
        'authorization_endpoint': authorization_endpoint,
        'token_endpoint': token_endpoint,
        'userinfo_endpoint': userinfo_endpoint,
        'jwks_uri': jwks_uri,
        'issuer': issuer,
    }


def _base64url_decode(value):
    padding_len = (-len(value)) % 4
    return base64.urlsafe_b64decode(value + ('=' * padding_len))


def _base64url_uint(value):
    return int.from_bytes(_base64url_decode(value), 'big')


def _load_jwt_part(value):
    return json.loads(_base64url_decode(value))


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


def fetch_jwks(jwks_uri):
    cached = app.config.get('_OIDC_JWKS_CACHE')
    now = time.time()
    if cached and cached['uri'] == jwks_uri and cached['expires_at'] > now:
        return cached['jwks']

    response = requests.get(jwks_uri, headers={'Accept': 'application/json'}, timeout=10)
    response.raise_for_status()
    jwks = response.json()
    app.config['_OIDC_JWKS_CACHE'] = {
        'uri': jwks_uri,
        'jwks': jwks,
        'expires_at': now + int(app.config.get('OIDC_JWKS_CACHE_SECONDS') or 3600),
    }
    return jwks


def _jwk_matches(header, jwk):
    if jwk.get('kty') != 'RSA':
        return False
    if jwk.get('use') not in (None, 'sig'):
        return False
    if header.get('kid') and jwk.get('kid') != header.get('kid'):
        return False
    if jwk.get('alg') and jwk.get('alg') != header.get('alg'):
        return False
    return True


def _public_key_from_jwk(jwk):
    if jwk.get('kty') != 'RSA':
        raise ValueError('unsupported JWK key type')
    numbers = rsa.RSAPublicNumbers(
        e=_base64url_uint(jwk['e']),
        n=_base64url_uint(jwk['n']),
    )
    return numbers.public_key()


def _verify_signature(header, signing_input, signature, jwks):
    alg = header.get('alg')
    allowed = app.config.get('OIDC_JWT_ALGORITHMS') or {'RS256'}
    if alg not in allowed or alg not in JWT_ALGORITHMS:
        raise ValueError('unsupported or disallowed JWT algorithm')

    candidates = [jwk for jwk in jwks.get('keys', []) if _jwk_matches(header, jwk)]
    if not candidates:
        raise ValueError('no matching JWK')

    verifier, hash_algorithm = JWT_ALGORITHMS[alg]
    for jwk in candidates:
        public_key = _public_key_from_jwk(jwk)
        try:
            public_key.verify(signature, signing_input, verifier, hash_algorithm)
            return
        except InvalidSignature:
            continue
    raise ValueError('invalid JWT signature')


def _validate_jwt_claims(claims):
    config = provider_config()
    now = int(time.time())
    leeway = int(app.config.get('OIDC_CLOCK_SKEW_SECONDS') or 60)
    client_id = app.config['OIDC_CLIENT_ID']

    if config.get('issuer') and claims.get('iss') != config['issuer']:
        raise ValueError('invalid JWT issuer')

    aud = claims.get('aud')
    if isinstance(aud, str):
        audiences = [aud]
    elif isinstance(aud, list):
        audiences = aud
    else:
        raise ValueError('missing JWT audience')
    if client_id not in audiences:
        raise ValueError('invalid JWT audience')
    if len(audiences) > 1 and claims.get('azp') not in (None, client_id):
        raise ValueError('invalid JWT authorized party')

    if not isinstance(claims.get('exp'), int) or now > claims['exp'] + leeway:
        raise ValueError('expired JWT')
    if 'nbf' in claims and isinstance(claims['nbf'], int) and now + leeway < claims['nbf']:
        raise ValueError('JWT not yet valid')
    if not isinstance(claims.get('iat'), int) or now + leeway < claims['iat']:
        raise ValueError('invalid JWT issued-at')

    expected_nonce = flask.session.pop('oidc_nonce', None)
    if not expected_nonce or not claims.get('nonce') or not secrets.compare_digest(expected_nonce, claims['nonce']):
        raise ValueError('invalid JWT nonce')


def validate_id_token(id_token):
    parts = id_token.split('.')
    if len(parts) != 3:
        raise ValueError('invalid JWT structure')
    header = _load_jwt_part(parts[0])
    claims = _load_jwt_part(parts[1])
    signing_input = f'{parts[0]}.{parts[1]}'.encode('ascii')
    signature = _base64url_decode(parts[2])

    config = provider_config()
    jwks = fetch_jwks(config['jwks_uri'])
    _verify_signature(header, signing_input, signature, jwks)
    _validate_jwt_claims(claims)
    return claims


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
    domain = models.db.session.get(models.Domain, domain_name)
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


def merge_userinfo_claims(id_token_claims, userinfo_claims):
    if userinfo_claims.get('sub') and id_token_claims.get('sub') != userinfo_claims.get('sub'):
        raise ValueError('UserInfo subject does not match ID token subject')
    claims = dict(id_token_claims)
    claims.update(userinfo_claims)
    return claims


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
        id_token = token.get('id_token')
        if not access_token or not id_token:
            flask.current_app.logger.warning('OIDC login failed: token response omitted access_token or id_token')
            return login_failed(_('OpenID Connect login failed'))
        claims = validate_id_token(id_token)
        userinfo = fetch_userinfo(access_token)
        user = login_user_from_claims(merge_userinfo_claims(claims, userinfo))
    except Exception:
        flask.current_app.logger.exception('OIDC login failed')
        return login_failed(_('OpenID Connect login failed'))

    if not user:
        return login_failed(_('OpenID Connect login failed'))

    destination = flask.session.pop('oidc_destination', None) or app.config['WEB_ADMIN']
    return flask.redirect(destination)
