"""Per-domain and per-mailbox Keycloak 2FA policy, and the email-first sign-in."""

from urllib.parse import parse_qs, urlsplit

import flask
import pytest

from mailu import keycloak, models
from mailu.internal import nginx

from .test_keycloak_sso import realm, start, finish  # noqa: F401  (fixture)


TOKEN = '0123456789abcdef' * 2


@pytest.fixture
def mailboxes(app, realm):
    """example.org requires 2FA by domain; other.org follows the default (off)."""
    app.config.update(KEYCLOAK_MFA_DEFAULT=False, AUTH_REQUIRE_TOKENS=False, WTF_CSRF_ENABLED=False)
    secure = models.Domain(name='example.org', mfa_required=True)
    plain = models.Domain(name='other.org')
    models.db.session.add_all([secure, plain])
    models.db.session.commit()
    users = {}
    for email, policy in (
        ('kc@example.org', None),        # domain: required
        ('legacy@example.org', False),   # mailbox exemption
        ('plain@other.org', None),       # default: not required
        ('boss@other.org', True),        # mailbox requirement
    ):
        localpart, domain = email.split('@')
        user = models.User(localpart=localpart, domain_name=domain, mfa_required=policy)
        user.set_password('password')
        models.db.session.add(user)
        models.db.session.commit()
        token = models.Token(user_email=user.email)
        token.set_password(TOKEN)
        models.db.session.add(token)
        models.db.session.commit()
        users[email] = user
    return users


def test_mailbox_overrides_domain_overrides_default(app, mailboxes):
    assert mailboxes['kc@example.org'].requires_mfa
    assert not mailboxes['legacy@example.org'].requires_mfa
    assert not mailboxes['plain@other.org'].requires_mfa
    assert mailboxes['boss@other.org'].requires_mfa
    # Unknown addresses follow their domain, so the answer reveals no mailbox.
    assert keycloak.mfa_required_for(email='nobody@example.org')
    assert not keycloak.mfa_required_for(email='nobody@other.org')
    assert not keycloak.mfa_required_for(email='nobody@unhosted.test')
    app.config['KEYCLOAK_MFA_DEFAULT'] = True
    assert mailboxes['plain@other.org'].requires_mfa
    assert not mailboxes['legacy@example.org'].requires_mfa
    assert keycloak.mfa_required_for(email='nobody@unhosted.test')


def test_policy_is_off_without_keycloak(app, mailboxes):
    app.config['KEYCLOAK_ISSUER'] = ''
    assert not mailboxes['boss@other.org'].requires_mfa
    with app.test_request_context():
        assert nginx.check_credentials(mailboxes['boss@other.org'], 'password', '203.0.113.5', 'imap', '993')


@pytest.mark.parametrize('email, required', [
    ('kc@example.org', True), ('legacy@example.org', False),
    ('plain@other.org', False), ('boss@other.org', True),
])
def test_mail_protocol_passwords_follow_the_mailbox_policy(app, mailboxes, email, required):
    user = mailboxes[email]
    with app.test_request_context():
        for protocol, port in (('imap', '993'), ('pop3', '995'), ('smtp', '465'), ('web', None)):
            user.enable_pop = True
            assert nginx.check_credentials(user, 'password', '203.0.113.5', protocol, port) is not required
            # App tokens keep working either way.
            assert nginx.check_credentials(user, TOKEN, '203.0.113.5', protocol, port)


def test_sign_in_page_asks_for_the_address_first(client, mailboxes):
    page = client.get('/sso/login')
    assert page.status_code == 200
    assert b'name="submitContinue"' in page.data
    assert b'name="pw"' not in page.data


@pytest.mark.parametrize('email', ['kc@example.org', 'boss@other.org', 'nobody@example.org'])
def test_address_requiring_2fa_continues_at_keycloak(client, realm, mailboxes, email):
    response = client.post('/sso/login', data={'email': email, 'submitContinue': 'Continue'})
    assert response.status_code == 302
    location = urlsplit(response.headers['Location'])
    assert location.path == '/sso/keycloak/login'
    assert parse_qs(location.query)['login_hint'] == [email]
    authorize = urlsplit(client.get(response.headers['Location']).headers['Location'])
    params = parse_qs(authorize.query)
    assert params['login_hint'] == [email]
    assert params['acr_values'] == ['mfa']


@pytest.mark.parametrize('email', ['legacy@example.org', 'plain@other.org', 'nobody@other.org'])
def test_exempt_address_continues_with_a_password(client, mailboxes, email):
    page = client.post('/sso/login', data={'email': email, 'submitContinue': 'Continue'})
    assert page.status_code == 200
    assert b'name="pw"' in page.data
    assert b'readonly' in page.data
    assert email.encode() in page.data


def test_exempt_mailbox_signs_in_with_a_password(client, mailboxes):
    response = client.post('/sso/login', data={
        'email': 'legacy@example.org', 'pw': 'password', 'submit': 'Sign in', 'destination': 'admin',
    })
    assert response.status_code == 302
    assert 'keycloak' not in response.headers['Location']
    flask.g.pop('_login_user', None)
    assert client.get('/internal/auth/user').status_code == 200


def test_password_form_for_a_2fa_mailbox_goes_to_keycloak(client, mailboxes):
    response = client.post('/sso/login', data={
        'email': 'kc@example.org', 'pw': 'password', 'submit': 'Sign in',
    })
    assert response.status_code == 302
    assert urlsplit(response.headers['Location']).path == '/sso/keycloak/login'
    assert client.get('/internal/auth/user').status_code == 403
    assert models.User.login('kc@example.org', 'password') is None
    assert models.User.login('legacy@example.org', 'password') is not None


def test_keycloak_sign_in_still_works_for_a_2fa_mailbox(client, realm, mailboxes):
    assert finish(client, start(client, realm)).status_code == 302
    with client.session_transaction() as session:
        assert session['_user_id'] == 'kc@example.org'
        assert session[keycloak.SESSION_AUTH_METHOD] == 'keycloak'


def test_password_sessions_survive_only_for_exempt_mailboxes(client, mailboxes):
    for email, status in (('legacy@example.org', 200), ('plain@other.org', 200),
                          ('kc@example.org', 403), ('boss@other.org', 403)):
        flask.g.pop('_login_user', None)
        with client.session_transaction() as session:
            session.clear()
            session['_user_id'] = email
            session['_fresh'] = True
            session[keycloak.SESSION_AUTH_METHOD] = 'password'
        assert client.get('/internal/auth/user').status_code == status, email


def test_passkey_sign_in_is_refused_for_2fa_addresses(client, mailboxes):
    response = client.post('/sso/passkey/options', json={'email': 'kc@example.org', 'target': 'webmail'})
    assert response.status_code == 403
    assert 'two-factor' in response.get_json()['error']
    exempt = {'email': 'legacy@example.org', 'target': 'webmail'}
    assert client.post('/sso/passkey/options', json=exempt).status_code == 200
    assert client.post('/sso/passkey/options', json={'email': '', 'target': 'webmail'}).status_code == 200


def test_without_exemptions_sign_in_goes_straight_to_keycloak(app, client, realm, mailboxes):
    app.config['KEYCLOAK_MFA_DEFAULT'] = True
    assert client.get('/sso/login').status_code == 200  # legacy@example.org is exempt
    mailboxes['legacy@example.org'].mfa_required = None
    models.db.session.commit()
    response = client.get('/sso/login')
    assert response.status_code == 302
    assert urlsplit(response.headers['Location']).path == '/sso/keycloak/login'
    assert client.post('/sso/passkey/options', json={'email': ''}).status_code == 403


def _sign_in_admin(client, user):
    flask.g.pop('_login_user', None)
    with client.session_transaction() as session:
        session.clear()
        session['_user_id'] = user.email
        session['_fresh'] = True
        session[keycloak.SESSION_AUTH_METHOD] = 'keycloak'


def _edit(client, user, policy):
    return client.post(f'/admin/user/edit/{user.email}', data={
        'quota_bytes': user.quota_bytes, 'enabled': 'y', 'enable_imap': 'y',
        'mfa_required': policy, 'submit': 'Save',
    })


def test_domain_manager_can_require_but_not_exempt(client, mailboxes):
    manager = mailboxes['boss@other.org']
    models.db.session.get(models.Domain, 'other.org').managers.append(manager)
    models.db.session.commit()
    target = mailboxes['plain@other.org']
    _sign_in_admin(client, manager)

    assert _edit(client, target, 'required').status_code == 302
    assert models.db.session.get(models.User, target.email).mfa_required is True

    flask.g.pop('_login_user', None)
    response = _edit(client, target, 'optional')
    assert response.status_code == 200
    assert b'Only global administrators can exempt' in response.data
    assert models.db.session.get(models.User, target.email).mfa_required is True

    flask.g.pop('_login_user', None)
    assert _edit(client, target, 'inherit').status_code == 302
    assert models.db.session.get(models.User, target.email).mfa_required is None


def test_global_admin_can_exempt_and_set_domain_policy(client, mailboxes):
    admin = mailboxes['boss@other.org']
    admin.global_admin = True
    models.db.session.commit()
    _sign_in_admin(client, admin)
    target = mailboxes['kc@example.org']
    assert _edit(client, target, 'optional').status_code == 302
    assert models.db.session.get(models.User, target.email).mfa_required is False

    flask.g.pop('_login_user', None)
    page = client.get('/admin/domain/edit/other.org')
    assert page.status_code == 200
    assert b'name="mfa_required"' in page.data

    flask.g.pop('_login_user', None)
    assert _edit(client, target, 'bogus').status_code == 200
    assert models.db.session.get(models.User, target.email).mfa_required is False


def test_api_reads_and_writes_the_policy(app, client, mailboxes):
    headers = {'Authorization': f'Bearer {app.config["API_TOKEN"]}'}
    response = client.patch('/api/v1/domain/other.org', json={'mfa_required': True}, headers=headers)
    assert response.status_code == 200, response.data
    assert models.db.session.get(models.Domain, 'other.org').mfa_required is True
    response = client.patch('/api/v1/domain/other.org', json={'mfa_required': None}, headers=headers)
    assert response.status_code == 200, response.data
    assert models.db.session.get(models.Domain, 'other.org').mfa_required is None
    assert client.patch('/api/v1/domain/other.org', json={'mfa_required': 'yes'}, headers=headers).status_code == 400

    response = client.patch('/api/v1/user/plain@other.org', json={'mfa_required': False}, headers=headers)
    assert response.status_code == 200, response.data
    assert models.db.session.get(models.User, 'plain@other.org').mfa_required is False
    assert client.get('/api/v1/user/plain@other.org', headers=headers).get_json()['mfa_required'] is False
    assert client.get('/api/v1/domain/example.org', headers=headers).get_json()['mfa_required'] is True
