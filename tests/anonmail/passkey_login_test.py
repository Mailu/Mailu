import re
import pytest
from datetime import datetime, timezone
from types import SimpleNamespace
from webauthn.helpers import bytes_to_base64url

from mailu import models


def get_csrf_token(client):
    response = client.get('/sso/login')
    return re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', response.data).group(1).decode()


@pytest.fixture
def user(app):
    domain = models.Domain(name='passkey-login.example')
    user = models.User(localpart='alice', domain=domain)
    user.set_password('test-password')
    models.db.session.add_all([domain, user])
    models.db.session.commit()
    return user


def test_passkey_options_allow_discoverable_login(client):
    response = client.post('/sso/passkey/options', json={})

    assert response.status_code == 200
    options = response.get_json()
    assert 'challenge' in options
    assert 'allowCredentials' not in options
    assert options['userVerification'] == 'required'


def test_passkey_options_reject_malformed_email_with_json_error(client):
    response = client.post('/sso/passkey/options', json={'email': 'not-an-email'})

    assert response.status_code == 400
    assert 'valid email address' in response.get_json()['error']


def test_passkey_options_and_status_are_not_rate_limited(client, monkeypatch, user):
    from mailu import utils

    monkeypatch.setattr(utils.limiter, 'should_rate_limit_ip', lambda *args: pytest.fail('passkey sign-in is not IP rate-limited'))
    monkeypatch.setattr(utils.limiter, 'should_rate_limit_user', lambda *args: pytest.fail('passkey sign-in is not user rate-limited'))

    options = client.post('/sso/passkey/options', json={'email': user.email})
    status = client.post('/sso/passkey/status', json={'email': user.email})

    assert options.status_code == 200
    assert status.status_code == 200


def test_login_page_supports_conditional_passkeys_and_destination_changes(client):
    response = client.get('/sso/login')

    assert response.status_code == 200
    assert b"mediation: 'conditional'" in response.data
    assert b"destinationField.addEventListener('change'" in response.data
    assert b"form.addEventListener('submit', cancelAttempt" in response.data
    assert b"submitButtons.forEach" in response.data


def test_password_login_redirects_after_nudge_flash(client, user):
    csrf_token = get_csrf_token(client)
    response = client.post('/sso/login', data={
        'csrf_token': csrf_token,
        'email': user.email,
        'pw': 'test-password',
        'submitAdmin': 'Sign in Admin',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert response.request.path != '/sso/login'
    assert b'Manage passkeys</a>' in response.data
    assert b'href="/admin/user/passkeys/' in response.data


def test_forced_password_reset_menu_offers_logout(client, user):
    user.change_pw_next_login = True
    models.db.session.commit()
    csrf_token = get_csrf_token(client)

    response = client.post('/sso/login', data={
        'csrf_token': csrf_token,
        'email': user.email,
        'pw': 'test-password',
        'submitAdmin': 'Sign in Admin',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert response.request.path == '/sso/pw_change'
    assert b'Sign out' in response.data
    assert b'href="/sso/logout"' in response.data
    assert b'Sign in' not in response.data


def test_manage_passkeys_page_has_a_name_form_and_sidebar_link(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = user.email
        session['_fresh'] = True

    response = client.get('/admin/user/passkeys')

    assert response.status_code == 200
    assert b'id="passkey-enrollment-form"' in response.data
    assert b'id="passkey-name"' in response.data
    assert f'href="/admin/user/passkeys/{user.email}"'.encode() in response.data
    assert b'window.prompt' not in response.data


def test_manage_passkeys_page_shows_creation_and_authenticator_details(client, user):
    models.db.session.add(models.Passkey(
        user=user,
        credential_id=b'detailed-credential',
        public_key=b'public-key',
        aaguid='adce0002-35bc-c60a-648b-0b25f1f05503',
        name='Travel laptop',
        user_verified=True,
        user_present=True,
        credential_device_type='multi_device',
        backup_eligible=True,
        backed_up=True,
        attestation_format='packed',
        device_bound=False,
        last_used_at=datetime(2025, 2, 3, 4, 5, tzinfo=timezone.utc),
    ))
    models.db.session.commit()
    with client.session_transaction() as session:
        session['_user_id'] = user.email
        session['_fresh'] = True

    response = client.get('/admin/user/passkeys')

    assert response.status_code == 200
    assert b'Travel laptop' in response.data
    assert b'Created' in response.data
    assert b'Last used' in response.data
    assert b'2025' in response.data
    assert b'Multi-device' in response.data
    assert b'Backed up' in response.data
    assert b'User present' in response.data
    assert b'User verified' in response.data
    assert b'Backup eligible' in response.data
    assert b'Attestation' in response.data
    assert b'Signature counter' in response.data
    assert b'Authenticator ID (AAGUID)' in response.data
    assert b'Yes' in response.data


def test_global_admin_can_open_target_users_passkey_routes(client, user):
    admin = models.User(localpart='admin', domain=user.domain, global_admin=True)
    admin.set_password('admin-password')
    models.db.session.add(admin)
    models.db.session.commit()
    with client.session_transaction() as session:
        session['_user_id'] = admin.email
        session['_fresh'] = True

    listing = client.get(f'/admin/user/passkeys/{user.email}')
    options = client.post(f'/admin/user/passkeys/{user.email}/options')

    assert listing.status_code == 200
    assert user.email.encode() in listing.data
    assert options.status_code == 200
    assert options.get_json()['user']['name'] == user.email


def test_user_edit_enrollment_link_is_copyable_not_clickable(client, user):
    admin = models.User(localpart='admin', domain=user.domain, global_admin=True)
    admin.set_password('admin-password')
    models.db.session.add(admin)
    models.db.session.commit()
    with client.session_transaction() as session:
        session['_user_id'] = admin.email
        session['_fresh'] = True
        session['new_account_setup_url'] = 'https://mail.example/sso/account/setup/one-time-token'
        session['new_account_setup_expires_at'] = datetime.now(timezone.utc)

    response = client.get(f'/admin/user/edit/{user.email}')

    assert response.status_code == 200
    assert b'Copy to clipboard' in response.data
    assert b'data-clipboard-target="#account-setup-link"' in response.data
    assert b'https://mail.example/sso/account/setup/one-time-token' in response.data
    assert b'href="https://mail.example/sso/account/setup/one-time-token"' not in response.data


def test_user_cannot_open_another_users_passkey_page(client, user):
    other = models.User(localpart='bob', domain=user.domain)
    other.set_password('other-password')
    models.db.session.add(other)
    models.db.session.commit()
    with client.session_transaction() as session:
        session['_user_id'] = other.email
        session['_fresh'] = True

    response = client.get(f'/admin/user/passkeys/{user.email}')

    assert response.status_code == 403


def test_domain_passkey_policy_renders_in_its_own_card(client, user):
    user.global_admin = True
    models.db.session.commit()
    with client.session_transaction() as session:
        session['_user_id'] = user.email
        session['_fresh'] = True

    response = client.get('/admin/domain/create')

    assert response.status_code == 200
    assert b'Passkey policy' in response.data
    assert b'Enforce AAGUID restrictions' in response.data
    assert b'id="passkey-aaguid-controls"' in response.data
    assert b'data-toggle-visibility="passkey_enforce_aaguid"' in response.data
    assert response.data.count(b'class="card card-outline card-primary"') >= 3


def test_user_list_shows_total_passkey_count(client, user):
    user.global_admin = True
    models.db.session.add_all([
        models.Passkey(
            user=user, credential_id=b'bound-key', public_key=b'public',
            aaguid='adce0002-35bc-c60a-648b-0b25f1f05503',
            name='First device',
        ),
        models.Passkey(
            user=user, credential_id=b'other-key', public_key=b'public',
            aaguid='adce0002-35bc-c60a-648b-0b25f1f05504',
            name='Second device',
        ),
    ])
    models.db.session.commit()
    with client.session_transaction() as session:
        session['_user_id'] = user.email
        session['_fresh'] = True

    response = client.get(f'/admin/user/list/{user.domain.name}')

    assert response.status_code == 200
    assert b'text-bg-primary">2</span>' in response.data
    assert b'not bound' not in response.data


def test_registration_accepts_webauthn_string_enum_values(client, user, monkeypatch, caplog):
    import logging
    from mailu.ui.views import passkeys as passkey_views

    caplog.set_level(logging.INFO)
    monkeypatch.setattr(
        passkey_views.webauthn_config, 'verify_registration_response',
        lambda **kwargs: SimpleNamespace(
            credential_id=b'credential-id',
            credential_public_key=b'public-key',
            sign_count=1,
            aaguid='adce0002-35bc-c60a-648b-0b25f1f05503',
            fmt='none',
            user_verified=False,
            credential_device_type='single_device',
            credential_backed_up=False,
        ),
    )
    monkeypatch.setattr(passkey_views.webauthn_config, 'authenticator_flags', lambda *args, **kwargs: SimpleNamespace(
        up=True, uv=False, be=False, bs=False,
    ))
    with client.session_transaction() as session:
        session['_user_id'] = user.email
        session['_fresh'] = True
        session['passkey_registration_challenge'] = bytes_to_base64url(b'test-challenge')
        session['passkey_registration_user'] = user.email

    response = client.post('/admin/user/passkeys', json={'id': 'credential', 'name': 'Test passkey'})

    assert response.status_code == 200
    credential = models.db.session.get(models.Passkey, b'credential-id')
    assert credential.device_bound is True
    assert credential.user_verified is False
    assert credential.user_present is True
    assert credential.credential_device_type == 'single_device'
    assert credential.backed_up is False
    assert 'Passkey registered' in caplog.text
    assert 'aaguid=adce0002-35bc-c60a-648b-0b25f1f05503' in caplog.text
    assert 'attestation=none' in caplog.text


def test_passkey_login_emits_password_style_audit_log(client, user, monkeypatch, caplog):
    import logging
    from mailu.sso.views import passkeys as sso_passkeys
    from mailu import utils

    caplog.set_level(logging.INFO)
    models.db.session.add(models.Passkey(
        user=user,
        credential_id=b'login-credential',
        public_key=b'public-key',
        sign_count=1,
        aaguid='adce0002-35bc-c60a-648b-0b25f1f05503',
        name='Test phone',
    ))
    models.db.session.commit()
    csrf_token = get_csrf_token(client)
    monkeypatch.setattr(sso_passkeys, 'verify_authentication_response', lambda **kwargs: SimpleNamespace(
        new_sign_count=2,
        user_verified=True,
        credential_device_type='single_device',
        credential_backed_up=False,
    ))
    monkeypatch.setattr(sso_passkeys.webauthn_config, 'authenticator_flags', lambda *args, **kwargs: SimpleNamespace(
        up=True, uv=True, be=False, bs=False,
    ))
    monkeypatch.setattr(utils.limiter, 'rate_limit_user', lambda *args, **kwargs: pytest.fail('passkey sign-in is not rate-limited'))
    with client.session_transaction() as session:
        session['passkey_login_challenge'] = bytes_to_base64url(b'test-challenge')
        session['passkey_login_email'] = user.email
        session['passkey_login_destination'] = '/admin/'

    response = client.post('/sso/passkey/verify', json={
        'id': bytes_to_base64url(b'login-credential'),
    }, headers={'X-CSRFToken': csrf_token})

    assert response.status_code == 200
    assert response.get_json()['redirect'] == '/admin/'
    assert any(
        cookie.startswith('rate_limit=') and 'Path=/sso/login' in cookie
        for cookie in response.headers.getlist('Set-Cookie')
    )
    credential = models.db.session.get(models.Passkey, b'login-credential')
    assert credential.user_verified is True
    assert credential.user_present is True
    assert credential.credential_device_type == 'single_device'
    assert credential.backed_up is False
    assert credential.last_used_at is not None
    assert f'Login attempt for: {user.email}/sso/' in caplog.text
    assert 'success: passkey:' in caplog.text


def test_passkey_login_rejects_aaguid_blocked_by_domain_policy(client, user, monkeypatch, caplog):
    import logging
    from mailu.sso.views import passkeys as sso_passkeys

    caplog.set_level(logging.WARNING)
    user.domain.passkey_aaguid_mode = 'block'
    user.domain.passkey_aaguids = 'adce0002-35bc-c60a-648b-0b25f1f05503'
    user.domain.passkey_enforce_aaguid = True
    models.db.session.add(models.Passkey(
        user=user,
        credential_id=b'blocked-credential',
        public_key=b'public-key',
        aaguid='adce0002-35bc-c60a-648b-0b25f1f05503',
    ))
    models.db.session.commit()
    csrf_token = get_csrf_token(client)
    monkeypatch.setattr(
        sso_passkeys, 'verify_authentication_response',
        lambda **kwargs: pytest.fail('Blocked AAGUID should be rejected before assertion verification'),
    )
    with client.session_transaction() as session:
        session['passkey_login_challenge'] = bytes_to_base64url(b'test-challenge')
        session['passkey_login_email'] = user.email

    response = client.post('/sso/passkey/verify', json={
        'id': bytes_to_base64url(b'blocked-credential'),
    }, headers={'X-CSRFToken': csrf_token})

    assert response.status_code == 401
    assert response.get_json()['error'] == 'Passkey sign-in failed.'
    assert 'reason=aaguid_policy' in caplog.text
