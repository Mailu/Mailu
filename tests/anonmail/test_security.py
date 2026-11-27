from urllib.parse import quote

import srslib

from mailu import models, quarantine, utils


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

    signup_url = f'{app.config["WEB_ADMIN"].rstrip("/")}/user/signup/signup-security.example'
    response = client.post(signup_url, data={
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
    user.change_pw_next_login = True
    models.db.session.add_all([domain, user])
    models.db.session.commit()

    inherited_session_client = app.test_client()
    password_change_client = app.test_client()
    for client in (inherited_session_client, password_change_client):
        # Establish the anonymous server-side session that a real login page
        # request would leave in each browser.
        with client.session_transaction():
            pass
        with app.app_context():
            login_response = client.post('/sso/login', data={
                'email': user.email,
                'pw': 'old-password',
            })
        assert login_response.status_code == 302

    with app.app_context():
        change_response = password_change_client.post('/sso/pw_change', data={
            'oldpw': 'old-password',
            'pw': 'new-password-123',
            'pw2': 'new-password-123',
        })

    assert change_response.status_code == 302
    with app.app_context():
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
    with app.app_context():
        assert browser.get('/sso/login').status_code == 200
        login_response = browser.post('/sso/login', data={
            'email': user.email,
            'pw': 'test-password',
        })
    assert login_response.status_code == 302

    user.enabled = False
    models.db.session.commit()
    assert models.User.get_active(user.email) is None
    with app.app_context():
        assert browser.get('/admin/admin/list').status_code == 302


    user.enabled = True
    models.db.session.commit()
    headers = {'Authorization': f'Bearer {app.config["API_TOKEN"]}'}
    with app.app_context():
        disable_response = api_client.patch(
            f'/api/v1/user/{user.email}', headers=headers, json={'enabled': False},
        )
    assert disable_response.status_code == 200
    with app.app_context():
        enable_response = api_client.patch(
            f'/api/v1/user/{user.email}', headers=headers, json={'enabled': True},
        )
    assert enable_response.status_code == 200

    with app.app_context():
        assert browser.get('/admin/admin/list').status_code == 302
def test_domain_manager_quarantine_access_requires_being_a_recipient(
    app, tmp_path, monkeypatch,
):
    monkeypatch.setattr(quarantine, 'directory', lambda: tmp_path)
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        domain = models.Domain(name='quarantine-access.example')
        manager = models.User(localpart='manager', domain=domain)
        other_user = models.User(localpart='other', domain=domain)
        domain.managers.append(manager)
        manager.set_password('test-password')
        other_user.set_password('test-password')
        models.db.session.add_all([domain, manager, other_user])
        models.db.session.commit()
        manager_email = manager.email
        other_email = other_user.email
        hidden_id = quarantine.store(
            b'Subject: private message\r\n\r\nbody',
            {'recipients': [other_email], 'subject': 'private message'},
        )
        visible_id = quarantine.store(
            b'Subject: manager copy\r\n\r\nbody',
            {'recipients': [manager_email], 'subject': 'manager copy'},
        )

    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = manager_email
        session['_fresh'] = True

    prefix = app.config['WEB_ADMIN']
    listing = client.get(f'{prefix}/quarantine')
    assert listing.status_code == 200
    assert b'private message' not in listing.data
    assert f'{prefix}/quarantine/{hidden_id}'.encode() not in listing.data
    assert client.get(f'{prefix}/quarantine/{hidden_id}').status_code == 404
    hidden_delete = f'{prefix}/quarantine/{hidden_id}/delete'
    assert client.get(hidden_delete).status_code == 404
    assert client.post(hidden_delete, data={'submit': 'Delete permanently'}).status_code == 404
    with app.app_context():
        assert quarantine.get(hidden_id) is not None

    assert client.get(f'{prefix}/quarantine/{visible_id}').status_code == 200
    visible_delete = f'{prefix}/quarantine/{visible_id}/delete'
    assert client.post(visible_delete, data={'submit': 'Delete permanently'}).status_code == 302
    with app.app_context():
        assert quarantine.get(visible_id) is None

