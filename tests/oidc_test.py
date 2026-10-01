import base64
import json
import time
from urllib.parse import parse_qs, urlparse

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa, utils

from mailu import models
from mailu.sso import oidc


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def b64url_uint(value):
    return b64url(value.to_bytes((value.bit_length() + 7) // 8, 'big'))


def jwk_from_private_key(private_key, kid='test-key'):
    numbers = private_key.public_key().public_numbers()
    return {
        'kty': 'RSA',
        'use': 'sig',
        'alg': 'RS256',
        'kid': kid,
        'n': b64url_uint(numbers.n),
        'e': b64url_uint(numbers.e),
    }


def jwk_from_ec_private_key(private_key, kid='test-ec-key'):
    numbers = private_key.public_key().public_numbers()
    return {
        'kty': 'EC',
        'use': 'sig',
        'alg': 'ES256',
        'kid': kid,
        'crv': 'P-256',
        'x': b64url_uint(numbers.x),
        'y': b64url_uint(numbers.y),
    }


def jwk_from_ed25519_private_key(private_key, kid='test-ed-key'):
    public_bytes = private_key.public_key().public_bytes_raw()
    return {
        'kty': 'OKP',
        'use': 'sig',
        'alg': 'EdDSA',
        'kid': kid,
        'crv': 'Ed25519',
        'x': b64url(public_bytes),
    }


def signed_es256_id_token(private_key, claims, kid='test-ec-key'):
    header = {'typ': 'JWT', 'alg': 'ES256', 'kid': kid}
    signing_input = '.'.join([
        b64url(json.dumps(header, separators=(',', ':')).encode('utf-8')),
        b64url(json.dumps(claims, separators=(',', ':')).encode('utf-8')),
    ])
    der_signature = private_key.sign(signing_input.encode('ascii'), ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der_signature)
    signature = r.to_bytes(32, 'big') + s.to_bytes(32, 'big')
    return f'{signing_input}.{b64url(signature)}'


def signed_eddsa_id_token(private_key, claims, kid='test-ed-key'):
    header = {'typ': 'JWT', 'alg': 'EdDSA', 'kid': kid}
    signing_input = '.'.join([
        b64url(json.dumps(header, separators=(',', ':')).encode('utf-8')),
        b64url(json.dumps(claims, separators=(',', ':')).encode('utf-8')),
    ])
    signature = private_key.sign(signing_input.encode('ascii'))
    return f'{signing_input}.{b64url(signature)}'


def signed_id_token(private_key, claims, kid='test-key'):
    header = {'typ': 'JWT', 'alg': 'RS256', 'kid': kid}
    signing_input = '.'.join([
        b64url(json.dumps(header, separators=(',', ':')).encode('utf-8')),
        b64url(json.dumps(claims, separators=(',', ':')).encode('utf-8')),
    ])
    signature = private_key.sign(signing_input.encode('ascii'), padding.PKCS1v15(), hashes.SHA256())
    return f'{signing_input}.{b64url(signature)}'


def configure_oidc(app):
    app.config.update({
        'OIDC_ENABLED': True,
        'OIDC_ISSUER': 'https://idp.example.test/',
        'OIDC_AUTHORIZATION_ENDPOINT': 'https://idp.example.test/authorize',
        'OIDC_TOKEN_ENDPOINT': 'https://idp.example.test/token',
        'OIDC_USERINFO_ENDPOINT': 'https://idp.example.test/userinfo',
        'OIDC_JWKS_URI': 'https://idp.example.test/jwks.json',
        'OIDC_CLIENT_ID': 'mailu',
        'OIDC_CLIENT_SECRET': 'secret',
        'OIDC_REDIRECT_URI': 'https://mail.example.test/sso/oidc/callback',
        'OIDC_SCOPES': 'openid email profile',
        'OIDC_EMAIL_CLAIM': 'email',
        'OIDC_REQUIRE_EMAIL_VERIFIED': True,
        'OIDC_CREATE_USER': False,
        'OIDC_ALLOWED_DOMAINS': set(),
        'OIDC_JWT_ALGORITHMS': {'EdDSA', 'ES256', 'RS256'},
        'OIDC_JWKS_CACHE_SECONDS': 3600,
        'OIDC_CLOCK_SKEW_SECONDS': 60,
    })


def create_domain_and_user(email='user@example.com'):
    domain_name = email.rsplit('@', 1)[1]
    domain = models.Domain(name=domain_name)
    models.db.session.add(domain)
    user = models.User(localpart=email.split('@', 1)[0], domain=domain)
    user.set_password('password')
    models.db.session.add(user)
    models.db.session.commit()
    return user


def id_token_claims(app, client, email='user@example.com', nonce=None):
    if nonce is None:
        with client.session_transaction() as session:
            nonce = session['oidc_nonce']
    now = int(time.time())
    return {
        'iss': app.config['OIDC_ISSUER'],
        'sub': email,
        'aud': app.config['OIDC_CLIENT_ID'],
        'exp': now + 300,
        'iat': now,
        'nonce': nonce,
        'email': email,
        'email_verified': True,
    }


def test_oidc_login_redirect_contains_state_and_pkce(app, client):
    configure_oidc(app)

    rv = client.get('/sso/oidc/login?url=/admin')

    assert rv.status_code == 302
    location = rv.headers['Location']
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert location.startswith('https://idp.example.test/authorize?')
    assert query['response_type'] == ['code']
    assert query['client_id'] == ['mailu']
    assert query['redirect_uri'] == ['https://mail.example.test/sso/oidc/callback']
    assert query['scope'] == ['openid email profile']
    assert query['code_challenge_method'] == ['S256']
    assert query.get('state')
    assert query.get('nonce')
    assert query.get('code_challenge')


def test_oidc_callback_validates_jwt_and_logs_in_existing_user(app, client, monkeypatch):
    configure_oidc(app)
    user = create_domain_and_user()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = {'keys': [jwk_from_private_key(private_key)]}

    captured = {}

    def fake_post(url, data=None, headers=None, auth=None, timeout=None):
        captured['token_request'] = data
        captured['auth'] = auth
        token = signed_id_token(private_key, id_token_claims(app, client, user.email))
        return FakeResponse({'access_token': 'access-token', 'id_token': token})

    def fake_get(url, headers=None, timeout=None):
        if url == app.config['OIDC_JWKS_URI']:
            return FakeResponse(jwks)
        assert headers['Authorization'] == 'Bearer access-token'
        return FakeResponse({'sub': user.email, 'email': user.email, 'email_verified': True})

    monkeypatch.setattr(oidc.requests, 'post', fake_post)
    monkeypatch.setattr(oidc.requests, 'get', fake_get)

    login = client.get('/sso/oidc/login?url=/admin')
    state = parse_qs(urlparse(login.headers['Location']).query)['state'][0]
    rv = client.get(f'/sso/oidc/callback?code=abc&state={state}')

    assert rv.status_code == 302
    assert urlparse(rv.headers['Location']).path == '/admin'
    assert captured['token_request']['code'] == 'abc'
    assert captured['token_request']['code_verifier']
    assert captured['auth'] == ('mailu', 'secret')
    with client.session_transaction() as session:
        assert session['_user_id'] == user.email


def test_oidc_callback_accepts_es256_id_token(app, client, monkeypatch):
    configure_oidc(app)
    user = create_domain_and_user()
    private_key = ec.generate_private_key(ec.SECP256R1())
    jwks = {'keys': [jwk_from_ec_private_key(private_key)]}

    monkeypatch.setattr(oidc.requests, 'post', lambda *args, **kwargs: FakeResponse({
        'access_token': 'access-token',
        'id_token': signed_es256_id_token(private_key, id_token_claims(app, client, user.email)),
    }))
    monkeypatch.setattr(oidc.requests, 'get', lambda *args, **kwargs: FakeResponse(jwks))

    login = client.get('/sso/oidc/login')
    state = parse_qs(urlparse(login.headers['Location']).query)['state'][0]
    rv = client.get(f'/sso/oidc/callback?code=abc&state={state}')

    assert rv.status_code == 302
    assert rv.headers['Location'] == '/admin'
    with client.session_transaction() as session:
        assert session['_user_id'] == user.email


def test_oidc_callback_accepts_eddsa_id_token(app, client, monkeypatch):
    configure_oidc(app)
    user = create_domain_and_user()
    private_key = ed25519.Ed25519PrivateKey.generate()
    jwks = {'keys': [jwk_from_ed25519_private_key(private_key)]}

    monkeypatch.setattr(oidc.requests, 'post', lambda *args, **kwargs: FakeResponse({
        'access_token': 'access-token',
        'id_token': signed_eddsa_id_token(private_key, id_token_claims(app, client, user.email)),
    }))
    monkeypatch.setattr(oidc.requests, 'get', lambda *args, **kwargs: FakeResponse(jwks))

    login = client.get('/sso/oidc/login')
    state = parse_qs(urlparse(login.headers['Location']).query)['state'][0]
    rv = client.get(f'/sso/oidc/callback?code=abc&state={state}')

    assert rv.status_code == 302
    assert rv.headers['Location'] == '/admin'
    with client.session_transaction() as session:
        assert session['_user_id'] == user.email


def test_oidc_callback_rejects_hs256_id_token(app, client, monkeypatch):
    configure_oidc(app)
    app.config['OIDC_JWT_ALGORITHMS'] = {'HS256', 'RS256'}
    user = create_domain_and_user()
    header = {'typ': 'JWT', 'alg': 'HS256', 'kid': 'symmetric'}
    claims = id_token_claims(app, client, user.email)
    signing_input = '.'.join([
        b64url(json.dumps(header, separators=(',', ':')).encode('utf-8')),
        b64url(json.dumps(claims, separators=(',', ':')).encode('utf-8')),
    ])
    token = f'{signing_input}.{b64url(b"not-a-valid-hmac")}'

    monkeypatch.setattr(oidc.requests, 'post', lambda *args, **kwargs: FakeResponse({
        'access_token': 'access-token',
        'id_token': token,
    }))
    monkeypatch.setattr(oidc.requests, 'get', lambda *args, **kwargs: FakeResponse({'keys': []}))

    login = client.get('/sso/oidc/login')
    state = parse_qs(urlparse(login.headers['Location']).query)['state'][0]
    rv = client.get(f'/sso/oidc/callback?code=abc&state={state}')

    assert rv.status_code == 302
    assert rv.headers['Location'] == '/sso/login'
    with client.session_transaction() as session:
        assert '_user_id' not in session


def test_oidc_callback_rejects_invalid_state(app, client, monkeypatch):
    configure_oidc(app)
    create_domain_and_user()

    def fail_post(*args, **kwargs):
        raise AssertionError('token endpoint should not be called for invalid state')

    monkeypatch.setattr(oidc.requests, 'post', fail_post)
    client.get('/sso/oidc/login')
    rv = client.get('/sso/oidc/callback?code=abc&state=wrong')

    assert rv.status_code == 302
    assert rv.headers['Location'] == '/sso/login'
    with client.session_transaction() as session:
        assert '_user_id' not in session


def test_oidc_callback_rejects_bad_jwt_signature(app, client, monkeypatch):
    configure_oidc(app)
    user = create_domain_and_user()
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = {'keys': [jwk_from_private_key(other_key)]}

    monkeypatch.setattr(oidc.requests, 'post', lambda *args, **kwargs: FakeResponse({
        'access_token': 'access-token',
        'id_token': signed_id_token(signing_key, id_token_claims(app, client, user.email)),
    }))
    monkeypatch.setattr(oidc.requests, 'get', lambda *args, **kwargs: FakeResponse(jwks))

    login = client.get('/sso/oidc/login')
    state = parse_qs(urlparse(login.headers['Location']).query)['state'][0]
    rv = client.get(f'/sso/oidc/callback?code=abc&state={state}')

    assert rv.status_code == 302
    assert rv.headers['Location'] == '/sso/login'
    with client.session_transaction() as session:
        assert '_user_id' not in session


def test_oidc_callback_rejects_bad_nonce(app, client, monkeypatch):
    configure_oidc(app)
    user = create_domain_and_user()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = {'keys': [jwk_from_private_key(private_key)]}

    monkeypatch.setattr(oidc.requests, 'post', lambda *args, **kwargs: FakeResponse({
        'access_token': 'access-token',
        'id_token': signed_id_token(private_key, id_token_claims(app, client, user.email, nonce='wrong')),
    }))
    monkeypatch.setattr(oidc.requests, 'get', lambda *args, **kwargs: FakeResponse(jwks))

    login = client.get('/sso/oidc/login')
    state = parse_qs(urlparse(login.headers['Location']).query)['state'][0]
    rv = client.get(f'/sso/oidc/callback?code=abc&state={state}')

    assert rv.status_code == 302
    assert rv.headers['Location'] == '/sso/login'
    with client.session_transaction() as session:
        assert '_user_id' not in session


def test_oidc_callback_rejects_userinfo_subject_mismatch(app, client, monkeypatch):
    configure_oidc(app)
    user = create_domain_and_user()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = {'keys': [jwk_from_private_key(private_key)]}

    monkeypatch.setattr(oidc.requests, 'post', lambda *args, **kwargs: FakeResponse({
        'access_token': 'access-token',
        'id_token': signed_id_token(private_key, id_token_claims(app, client, user.email)),
    }))

    def fake_get(url, headers=None, timeout=None):
        if url == app.config['OIDC_JWKS_URI']:
            return FakeResponse(jwks)
        return FakeResponse({'sub': 'other@example.com', 'email': user.email, 'email_verified': True})

    monkeypatch.setattr(oidc.requests, 'get', fake_get)

    login = client.get('/sso/oidc/login')
    state = parse_qs(urlparse(login.headers['Location']).query)['state'][0]
    rv = client.get(f'/sso/oidc/callback?code=abc&state={state}')

    assert rv.status_code == 302
    assert rv.headers['Location'] == '/sso/login'
    with client.session_transaction() as session:
        assert '_user_id' not in session


def test_oidc_callback_can_create_domain_user_when_enabled(app, client, monkeypatch):
    configure_oidc(app)
    app.config['OIDC_CREATE_USER'] = True
    app.config['OIDC_ALLOWED_DOMAINS'] = {'example.com'}
    domain = models.Domain(name='example.com')
    models.db.session.add(domain)
    models.db.session.commit()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = {'keys': [jwk_from_private_key(private_key)]}

    monkeypatch.setattr(oidc.requests, 'post', lambda *args, **kwargs: FakeResponse({
        'access_token': 'access-token',
        'id_token': signed_id_token(private_key, id_token_claims(app, client, 'new@example.com')),
    }))

    def fake_get(url, headers=None, timeout=None):
        if url == app.config['OIDC_JWKS_URI']:
            return FakeResponse(jwks)
        return FakeResponse({'sub': 'new@example.com', 'email': 'new@example.com', 'email_verified': True})

    monkeypatch.setattr(oidc.requests, 'get', fake_get)

    login = client.get('/sso/oidc/login')
    state = parse_qs(urlparse(login.headers['Location']).query)['state'][0]
    rv = client.get(f'/sso/oidc/callback?code=abc&state={state}')

    assert rv.status_code == 302
    assert rv.headers['Location'] == '/admin'
    user = models.User.get('new@example.com')
    assert user is not None
    assert user.enabled is True
    with client.session_transaction() as session:
        assert session['_user_id'] == 'new@example.com'
