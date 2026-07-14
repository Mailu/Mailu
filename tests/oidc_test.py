from urllib.parse import parse_qs, urlparse

from mailu import models
from mailu.sso import oidc


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def configure_oidc(app):
    app.config.update({
        'OIDC_ENABLED': True,
        'OIDC_AUTHORIZATION_ENDPOINT': 'https://idp.example.test/authorize',
        'OIDC_TOKEN_ENDPOINT': 'https://idp.example.test/token',
        'OIDC_USERINFO_ENDPOINT': 'https://idp.example.test/userinfo',
        'OIDC_CLIENT_ID': 'mailu',
        'OIDC_CLIENT_SECRET': 'secret',
        'OIDC_REDIRECT_URI': 'https://mail.example.test/sso/oidc/callback',
        'OIDC_SCOPES': 'openid email profile',
        'OIDC_EMAIL_CLAIM': 'email',
        'OIDC_REQUIRE_EMAIL_VERIFIED': True,
        'OIDC_CREATE_USER': False,
        'OIDC_ALLOWED_DOMAINS': set(),
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


def test_oidc_callback_logs_in_existing_user(app, client, monkeypatch):
    configure_oidc(app)
    user = create_domain_and_user()

    captured = {}

    def fake_post(url, data=None, headers=None, auth=None, timeout=None):
        captured['token_request'] = data
        captured['auth'] = auth
        return FakeResponse({'access_token': 'access-token'})

    def fake_get(url, headers=None, timeout=None):
        assert headers['Authorization'] == 'Bearer access-token'
        return FakeResponse({'email': user.email, 'email_verified': True})

    monkeypatch.setattr(oidc.requests, 'post', fake_post)
    monkeypatch.setattr(oidc.requests, 'get', fake_get)

    login = client.get('/sso/oidc/login?url=/admin')
    state = parse_qs(urlparse(login.headers['Location']).query)['state'][0]
    rv = client.get(f'/sso/oidc/callback?code=abc&state={state}')

    assert rv.status_code == 302
    assert rv.headers['Location'] == '/admin'
    assert captured['token_request']['code'] == 'abc'
    assert captured['token_request']['code_verifier']
    assert captured['auth'] == ('mailu', 'secret')
    with client.session_transaction() as session:
        assert session['_user_id'] == user.email


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


def test_oidc_callback_can_create_domain_user_when_enabled(app, client, monkeypatch):
    configure_oidc(app)
    app.config['OIDC_CREATE_USER'] = True
    app.config['OIDC_ALLOWED_DOMAINS'] = {'example.com'}
    domain = models.Domain(name='example.com')
    models.db.session.add(domain)
    models.db.session.commit()

    monkeypatch.setattr(oidc.requests, 'post', lambda *args, **kwargs: FakeResponse({'access_token': 'access-token'}))
    monkeypatch.setattr(oidc.requests, 'get', lambda *args, **kwargs: FakeResponse({'email': 'new@example.com', 'email_verified': True}))

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
