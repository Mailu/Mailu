from urllib.parse import quote

import srslib

from mailu import models, utils


def test_sso_rate_limit_is_shared_by_email_case_variants(app):
    app.config['AUTH_RATELIMIT_USER'] = '1/day'
    email = 'CaseAudit@example.com'
    client_ip = '198.51.100.27'

    utils.limiter.rate_limit_user(email, client_ip, password='incorrect')

    assert utils.limiter.should_rate_limit_user(email.lower(), client_ip)


def test_public_signup_rejects_slash_localpart(app, client):
    app.config['WTF_CSRF_ENABLED'] = False
    domain = models.Domain(name='signup-security.example', signup_enabled=True)
    models.db.session.add(domain)
    models.db.session.commit()

    response = client.post('/user/signup/signup-security.example', data={
        'localpart': '/victim',
        'signup_method': 'passkey',
    })

    assert response.status_code == 200
    assert models.User.query.count() == 0


def test_postfix_recipient_map_rejects_short_srs_hash(app, client):
    sender = 'probe@example.net'
    valid_srs_address = srslib.SRS(app.srs_key).forward(sender, 'mailu.example')
    full_hash_response = client.get(
        f'/internal/postfix/recipient/map/{quote(valid_srs_address, safe="")}'
    )

    assert full_hash_response.status_code == 200
    assert full_hash_response.get_json() == sender

    localpart, domain = valid_srs_address.rsplit('@', 1)
    prefix, hash_value, remainder = localpart.split('=', 2)
    short_hash_address = f'{prefix}={hash_value[0]}={remainder}@{domain}'
    short_hash_response = client.get(
        f'/internal/postfix/recipient/map/{quote(short_hash_address, safe="")}'
    )

    assert short_hash_response.status_code == 404


def test_password_change_revokes_sessions_created_from_anonymous_sessions(app):
    app.config['WTF_CSRF_ENABLED'] = False
    domain = models.Domain(name='session-security.example')
    user = models.User(localpart='admin', domain=domain, global_admin=True)
    user.set_password('old-password')
    models.db.session.add_all([domain, user])
    models.db.session.commit()

    inherited_session_client = app.test_client()
    password_change_client = app.test_client()
    for client in (inherited_session_client, password_change_client):
        assert client.get('/sso/login').status_code == 200
        login_response = client.post('/sso/login', data={
            'email': user.email,
            'pw': 'old-password',
        })
        assert login_response.status_code == 302

    change_response = password_change_client.post('/sso/pw_change', data={
        'oldpw': 'old-password',
        'pw': 'new-password-123',
        'pw2': 'new-password-123',
    })

    assert change_response.status_code == 302
    assert inherited_session_client.get('/sso/pw_change').status_code == 302


def test_disabling_global_admin_revokes_existing_sessions(app):
    app.config['WTF_CSRF_ENABLED'] = False
    domain = models.Domain(name='disabled-session-security.example')
    user = models.User(localpart='admin', domain=domain, global_admin=True)
    user.set_password('test-password')
    models.db.session.add_all([domain, user])
    models.db.session.commit()

    browser = app.test_client()
    api_client = app.test_client()
    assert browser.get('/sso/login').status_code == 200
    login_response = browser.post('/sso/login', data={
        'email': user.email,
        'pw': 'test-password',
    })
    assert login_response.status_code == 302

    user.enabled = False
    models.db.session.commit()
    assert browser.get('/admin/admin/list').status_code == 302

    user.enabled = True
    models.db.session.commit()
    headers = {'Authorization': f'Bearer {app.config["API_TOKEN"]}'}
    disable_response = api_client.patch(
        f'/api/v1/user/{user.email}', headers=headers, json={'enabled': False},
    )
    assert disable_response.status_code == 200
    enable_response = api_client.patch(
        f'/api/v1/user/{user.email}', headers=headers, json={'enabled': True},
    )
    assert enable_response.status_code == 200

    assert browser.get('/admin/admin/list').status_code == 302
