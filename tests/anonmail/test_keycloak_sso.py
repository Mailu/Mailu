"""Keycloak OpenID Connect sign-in with enforced two-factor authentication."""

import json
import time
from urllib.parse import parse_qs, urlencode, urlsplit

import flask
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from mailu import keycloak, models
from mailu.internal import nginx


ISSUER = 'https://sso.example.org/realms/mail'
CLIENT_ID = 'mailu'


class FakeKeycloak:
    """A Keycloak realm that signs ID tokens with a real RSA key."""

    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        jwk.update(kid='realm-key', use='sig', alg='RS256')
        self.jwks = {'keys': [jwk, {'kid': 'enc-key', 'use': 'enc', 'kty': 'RSA', 'n': 'AQAB', 'e': 'AQAB'}]}
        self.claims = {}
        self.token_status = 200
        self.token_requests = []
        self.signing_key = self.key
        self.kid = 'realm-key'
        self.codes = {}

    def metadata(self):
        return {
            'issuer': ISSUER,
            'authorization_endpoint': f'{ISSUER}/protocol/openid-connect/auth',
            'token_endpoint': f'{ISSUER}/protocol/openid-connect/token',
            'jwks_uri': f'{ISSUER}/protocol/openid-connect/certs',
            'end_session_endpoint': f'{ISSUER}/protocol/openid-connect/logout',
        }

    def get(self, url):
        if url == f'{ISSUER}/.well-known/openid-configuration':
            return self.metadata()
        if url == self.metadata()['jwks_uri']:
            return self.jwks
        raise AssertionError(f'unexpected GET {url}')

    def post(self, url, data):
        assert url == self.metadata()['token_endpoint']
        self.token_requests.append(dict(data))
        if self.token_status != 200:
            return self.token_status, {'error': 'invalid_grant'}
        nonce = self.codes[data['code']]
        now = int(time.time())
        claims = {
            'iss': ISSUER, 'aud': CLIENT_ID, 'azp': CLIENT_ID, 'sub': 'kc-user-1',
            'iat': now, 'exp': now + 300, 'nonce': nonce,
            'email': 'kc@example.org', 'email_verified': True, 'acr': 'mfa',
        }
        claims.update(self.claims)
        claims = {key: value for key, value in claims.items() if value is not None}
        token = jwt.encode(claims, self.signing_key, algorithm='RS256', headers={'kid': self.kid})
        return 200, {'id_token': token, 'access_token': 'unused', 'token_type': 'Bearer'}


@pytest.fixture
def realm(app, monkeypatch):
    fake = FakeKeycloak()
    monkeypatch.setattr(keycloak, '_http_get', fake.get)
    monkeypatch.setattr(keycloak, '_http_post', fake.post)
    app.config.update(
        KEYCLOAK_ISSUER=ISSUER,
        KEYCLOAK_CLIENT_ID=CLIENT_ID,
        KEYCLOAK_CLIENT_SECRET='client-secret',
        KEYCLOAK_MFA_DEFAULT=True,
        KEYCLOAK_REQUIRED_ACR='mfa',
        KEYCLOAK_REQUIRED_AMR='',
        KEYCLOAK_CREATE_USERS=False,
        HOSTNAME='mail.example.org',
        HOSTNAMES='mail.example.org',
        TLS_FLAVOR='cert',
    )
    app.keycloak_cache = {}
    return fake


@pytest.fixture
def kc_user(create_user_and_token):
    user, token = create_user_and_token(email='kc@example.org', token_str='0123456789abcdef' * 2)
    return user


def start(client, realm, path='/sso/keycloak/login'):
    response = client.get(path)
    assert response.status_code == 302
    location = urlsplit(response.headers['Location'])
    assert f'{location.scheme}://{location.netloc}{location.path}' == realm.metadata()['authorization_endpoint']
    params = {key: values[0] for key, values in parse_qs(location.query).items()}
    realm.codes['the-code'] = params['nonce']
    return params


def finish(client, params, code='the-code', **extra):
    query = {'code': code, 'state': params['state'], **extra}
    callback = client.get('/sso/keycloak/callback', query_string=query)
    assert callback.status_code == 200
    # The bounce page must not set (and so replace) the Strict session cookie.
    assert 'Set-Cookie' not in callback.headers
    target = urlsplit(callback.headers.get('Refresh') or _meta_refresh(callback.data))
    return client.get(target.path, query_string=target.query)


def _meta_refresh(body):
    marker = b'content="0;url='
    start_at = body.index(marker) + len(marker)
    return body[start_at:body.index(b'"', start_at)].decode().replace('&amp;', '&')


def test_authorization_request_uses_pkce_state_nonce_and_acr(client, realm):
    params = start(client, realm)
    assert params['client_id'] == CLIENT_ID
    assert params['response_type'] == 'code'
    assert params['code_challenge_method'] == 'S256'
    assert len(params['code_challenge']) == 43
    assert params['acr_values'] == 'mfa'
    assert params['redirect_uri'] == 'https://mail.example.org/sso/keycloak/callback'
    assert 'openid' in params['scope'].split()
    assert params['state'] != params['nonce']


def test_mfa_sign_in_creates_trusted_session(app, client, realm, kc_user):
    params = start(client, realm, '/sso/keycloak/login?target=admin')
    response = finish(client, params)
    assert response.status_code == 302
    assert response.headers['Location'] == app.config['WEB_ADMIN']
    token_request = realm.token_requests[0]
    assert token_request['client_secret'] == 'client-secret'
    assert len(token_request['code_verifier']) >= 43
    with client.session_transaction() as session:
        assert session['_user_id'] == kc_user.email
        assert session[keycloak.SESSION_AUTH_METHOD] == 'keycloak'
        assert keycloak.SESSION_PENDING not in session
    # The session works for nginx's webmail/admin auth_request checks.
    assert client.get('/internal/auth/user').status_code == 200


@pytest.mark.parametrize('claims, config', [
    ({'acr': '1'}, {}),
    ({'acr': None}, {}),
    ({'amr': ['pwd']}, {'KEYCLOAK_REQUIRED_ACR': '', 'KEYCLOAK_REQUIRED_AMR': 'otp,hwk'}),
])
def test_sign_in_without_second_factor_is_rejected(app, client, realm, kc_user, claims, config):
    app.config.update(config)
    realm.claims = claims
    params = start(client, realm)
    response = finish(client, params)
    assert response.status_code == 400
    assert b'two-factor' in response.data
    assert client.get('/internal/auth/user').status_code == 403


def test_amr_policy_accepts_listed_method(app, client, realm, kc_user):
    app.config.update(KEYCLOAK_REQUIRED_ACR='', KEYCLOAK_REQUIRED_AMR='otp,hwk')
    realm.claims = {'acr': '1', 'amr': ['pwd', 'otp']}
    assert finish(client, start(client, realm)).status_code == 302


@pytest.mark.parametrize('tamper', ['nonce', 'aud', 'iss', 'expired', 'signature', 'azp', 'unverified', 'no_email'])
def test_untrusted_id_tokens_are_rejected(app, client, realm, kc_user, tamper):
    if tamper == 'nonce':
        realm.claims = {'nonce': 'other'}
    elif tamper == 'aud':
        realm.claims = {'aud': 'another-client', 'azp': 'another-client'}
    elif tamper == 'iss':
        realm.claims = {'iss': 'https://evil.example.org/realms/mail'}
    elif tamper == 'expired':
        realm.claims = {'exp': int(time.time()) - 3600, 'iat': int(time.time()) - 7200}
    elif tamper == 'signature':
        realm.signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    elif tamper == 'azp':
        realm.claims = {'aud': [CLIENT_ID, 'other'], 'azp': 'other'}
    elif tamper == 'unverified':
        realm.claims = {'email_verified': False}
    elif tamper == 'no_email':
        realm.claims = {'email': None}
    params = start(client, realm)
    response = finish(client, params)
    assert response.status_code == 400
    assert client.get('/internal/auth/user').status_code == 403


def test_unknown_state_and_replayed_state_are_rejected(client, realm, kc_user):
    params = start(client, realm)
    forged = dict(params, state='forged')
    assert finish(client, forged).status_code == 400
    assert finish(client, params).status_code == 302
    client.get('/sso/logout')
    # The state was consumed by the successful sign-in.
    assert finish(client, params).status_code == 400


def test_provider_error_and_mismatched_issuer_are_rejected(client, realm, kc_user):
    params = start(client, realm)
    response = finish(client, params, error='access_denied')
    assert response.status_code == 400
    assert realm.token_requests == []
    params = start(client, realm)
    assert finish(client, params, iss='https://evil.example.org').status_code == 400
    assert realm.token_requests == []


def test_token_endpoint_failure_is_reported(client, realm, kc_user):
    realm.token_status = 400
    assert finish(client, start(client, realm)).status_code == 400


def test_unknown_mailbox_is_rejected_unless_provisioning(app, client, realm):
    params = start(client, realm)
    response = finish(client, params)
    assert response.status_code == 400
    assert b'no mailbox' in response.data

    models.db.session.add(models.Domain(name='example.org'))
    models.db.session.commit()
    app.config['KEYCLOAK_CREATE_USERS'] = True
    params = start(client, realm)
    assert finish(client, params).status_code == 302
    assert models.User.get('kc@example.org') is not None


def test_disabled_mailbox_is_rejected(client, realm, kc_user):
    kc_user.enabled = False
    models.db.session.commit()
    assert finish(client, start(client, realm)).status_code == 400


def test_keycloak_only_redirects_login_and_blocks_local_methods(app, client, realm, kc_user):
    response = client.get('/sso/login/webmail')
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/sso/keycloak/login')

    app.config['WTF_CSRF_ENABLED'] = False
    response = client.post('/sso/login', data={'email': kc_user.email, 'pw': 'password', 'submit': 'Sign in'})
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/sso/keycloak/login')
    assert client.get('/internal/auth/user').status_code == 403

    assert client.post('/sso/passkey/options', json={}).status_code == 403
    assert client.post('/sso/passkey/verify', json={}).status_code == 403
    assert models.User.login(kc_user.email, 'password') is None


def test_keycloak_only_ignores_sessions_not_created_by_keycloak(client, realm, kc_user):
    with client.session_transaction() as session:
        session['_user_id'] = kc_user.email
        session['_fresh'] = True
    assert client.get('/internal/auth/user').status_code == 403
    for method, status in (('password', 403), ('keycloak', 200), ('proxy', 200)):
        # The fixture's long-lived app context would keep Flask-Login's
        # per-request user cache; production requests start without it.
        flask.g.pop('_login_user', None)
        with client.session_transaction() as session:
            session[keycloak.SESSION_AUTH_METHOD] = method
        assert client.get('/internal/auth/user').status_code == status, method


@pytest.mark.parametrize('protocol, port', [
    ('imap', '993'), ('pop3', '995'), ('smtp', '465'), ('submission', '587'), ('sieve', '4190'), ('web', None),
])
def test_keycloak_only_rejects_mailbox_passwords_but_accepts_app_tokens(app, realm, kc_user, protocol, port):
    kc_user.enable_pop = True
    with app.test_request_context():
        assert not nginx.check_credentials(kc_user, 'password', '203.0.113.5', protocol, port)
        assert nginx.check_credentials(kc_user, '0123456789abcdef' * 2, '203.0.113.5', protocol, port)


def test_passwords_still_work_when_2fa_is_not_required_by_default(app, client, realm, kc_user):
    app.config.update(KEYCLOAK_MFA_DEFAULT=False, AUTH_REQUIRE_TOKENS=False, WTF_CSRF_ENABLED=False)
    with app.test_request_context():
        assert nginx.check_credentials(kc_user, 'password', '203.0.113.5', 'imap', '993')
    page = client.get('/sso/login')
    assert page.status_code == 200
    assert b'/sso/keycloak/login' in page.data
    assert b'Sign in with Keycloak' in page.data
    # The address comes first; the password field appears on the next step.
    assert b'name="submitContinue"' in page.data
    assert b'name="pw"' not in page.data


def test_logout_ends_the_keycloak_session(client, realm, kc_user):
    finish(client, start(client, realm))
    with client.session_transaction() as session:
        id_token = session[keycloak.SESSION_ID_TOKEN]
    response = client.get('/sso/logout')
    assert response.status_code == 302
    location = urlsplit(response.headers['Location'])
    assert f'{location.scheme}://{location.netloc}{location.path}' == realm.metadata()['end_session_endpoint']
    params = {key: values[0] for key, values in parse_qs(location.query).items()}
    assert params['id_token_hint'] == id_token
    assert params['client_id'] == CLIENT_ID
    assert params['post_logout_redirect_uri'] == 'https://mail.example.org/sso/login'
    assert client.get('/internal/auth/user').status_code == 403


def test_oauth_consent_for_mail_clients_goes_through_keycloak(client, realm, kc_user):
    authorize = '/admin/oauth2/authorize?' + urlencode({
        'client_id': 'mailu', 'response_type': 'code',
        'redirect_uri': 'http://127.0.0.1:49152/', 'scope': 'imap smtp',
        'code_challenge': 'A' * 43, 'code_challenge_method': 'S256', 'state': 's',
    })
    response = client.get(authorize)
    assert response.status_code == 302
    response = client.get(urlsplit(response.headers['Location']).path)
    assert response.headers['Location'].endswith('/sso/keycloak/login')
    params = start(client, realm)
    response = finish(client, params)
    assert response.status_code == 302
    assert urlsplit(response.headers['Location']).path == '/admin/oauth2/authorize'
    consent = client.get(response.headers['Location'])
    assert consent.status_code == 200
    assert kc_user.email.encode() in consent.data


def test_disabled_without_issuer(app, client):
    app.config['KEYCLOAK_ISSUER'] = ''
    assert client.get('/sso/keycloak/login').status_code == 404
    assert client.get('/sso/keycloak/callback').status_code == 404
    assert client.get('/sso/keycloak/finish').status_code == 404
    assert not keycloak.mfa_required_for(email='kc@example.org')
    assert keycloak.mfa_exemptions_exist()


def test_signing_key_rotation_is_picked_up(app, client, realm, kc_user, monkeypatch):
    finish(client, start(client, realm))
    client.get('/sso/logout')
    rotated = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(rotated.public_key()))
    jwk.update(kid='rotated-key', use='sig')  # no "alg": PS256 must still verify
    realm.jwks = {'keys': realm.jwks['keys'] + [jwk]}
    realm.signing_key, realm.kid = rotated, 'rotated-key'
    original_post = realm.post

    def post_ps256(url, data):
        status, body = original_post(url, data)
        claims = jwt.decode(body['id_token'], options={'verify_signature': False})
        body['id_token'] = jwt.encode(claims, rotated, algorithm='PS256', headers={'kid': 'rotated-key'})
        return status, body
    monkeypatch.setattr(keycloak, '_http_post', post_ps256)
    # The JWKS was just fetched; a refresh is allowed once the minimum interval passed.
    app.keycloak_cache['jwks'] = (0, app.keycloak_cache['jwks'][1])
    assert finish(client, start(client, realm)).status_code == 302


def test_unsigned_id_token_is_rejected(client, realm, kc_user, monkeypatch):
    original_post = realm.post

    def post_unsigned(url, data):
        status, body = original_post(url, data)
        claims = jwt.decode(body['id_token'], options={'verify_signature': False})
        body['id_token'] = jwt.encode(claims, None, algorithm='none', headers={'kid': 'realm-key'})
        return status, body
    monkeypatch.setattr(keycloak, '_http_post', post_unsigned)
    assert finish(client, start(client, realm)).status_code == 400
    assert client.get('/internal/auth/user').status_code == 403
