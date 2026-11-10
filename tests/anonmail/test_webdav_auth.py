"""Keep browser, device and internal webmail DAV authentication separate."""
import base64

import pytest

from mailu import models


@pytest.fixture
def dav_user(app, client):
    models.db.session.add(models.Domain(name='example.org'))
    user = models.User(localpart='alice', domain_name='example.org')
    user.set_password('correct-password')
    models.db.session.add(user)
    models.db.session.commit()
    with client.session_transaction() as session:
        session['_user_id'] = user.get_id()
        session['_fresh'] = True
    return user


def basic(email, password):
    return 'Basic ' + base64.b64encode(f'{email}:{password}'.encode()).decode()


@pytest.mark.parametrize('method', ['PROPFIND', 'MKCOL', 'PUT', 'DELETE', 'POST'])
def test_browser_dav_requires_same_origin_for_session_requests(client, dav_user, method):
    headers = {'X-Mailu-Original-Method': method, 'X-Mailu-Auth-Context': 'webdav'}
    assert client.get('/internal/auth/basic', headers=headers).status_code == 401
    for site in ['cross-site', 'same-site', 'none']:
        headers['Sec-Fetch-Site'] = site
        assert client.get('/internal/auth/basic', headers=headers).status_code == 401
    headers['Sec-Fetch-Site'] = 'same-origin'
    response = client.get('/internal/auth/basic', headers=headers)
    assert response.status_code == 200
    assert response.headers['X-User'] == dav_user.email


def test_explicit_credentials_never_fall_back_to_browser_session(client, dav_user):
    response = client.get('/internal/auth/basic', headers={
        'X-Mailu-Auth-Context': 'webdav',
        'X-Mailu-Original-Method': 'GET', 'Sec-Fetch-Site': 'same-origin',
        'Authorization': basic(dav_user.email, 'wrong-password'),
    })
    assert response.status_code == 401
    assert 'WWW-Authenticate' in response.headers
    assert client.get('/internal/auth/basic', headers={
        'Authorization': basic(dav_user.email, 'correct-password'),
    }).status_code == 200


def test_webmail_session_token_is_internal_and_revocable(client, dav_user):
    token = client.get('/internal/auth/user').headers['X-User-Token']
    headers = {
        'Authorization': basic(dav_user.email, token),
        'X-Mailu-Auth-Context': 'webdav',
        'X-Forwarded-By': '192.168.203.10',
    }
    webmail_headers = {key: value for key, value in headers.items() if key != 'Authorization'}
    assert client.get('/internal/auth/basic', headers=headers).status_code == 200
    # The token remains valid while its owning Mailu session exists.
    assert client.get('/internal/auth/basic', headers=headers).status_code == 200
    assert client.get('/internal/auth/basic', headers={
        **headers, 'X-Forwarded-By': '203.0.113.10',
    }).status_code == 401
    assert client.get('/internal/auth/basic', headers={
        'Authorization': basic(dav_user.email, 'correct-password'),
        **webmail_headers,
    }).status_code == 200
    with client.session_transaction() as session:
        session.clear()
    assert client.get('/internal/auth/basic', headers=headers).status_code == 401


def test_private_webmail_listener_accepts_session_token(client, dav_user):
    token = client.get('/internal/auth/user').headers['X-User-Token']
    response = client.get('/internal/auth/basic', headers={
        'Authorization': basic(dav_user.email, token),
        'X-Mailu-Auth-Context': 'webdav-internal',
        'X-Forwarded-By': '172.20.0.2',
    })
    assert response.status_code == 200
    assert response.headers['X-User'] == dav_user.email


def test_disabled_users_and_identity_headers_cannot_authenticate(app, client, dav_user):
    token = client.get('/internal/auth/user').headers['X-User-Token']
    dav_user.enabled = False
    models.db.session.commit()
    assert client.get('/internal/auth/basic', headers={
        'X-Mailu-Auth-Context': 'webdav',
        'X-Mailu-Original-Method': 'GET', 'X-Remote-User': dav_user.email,
    }).status_code == 401
    assert client.get('/internal/auth/basic', headers={
        'Authorization': basic(dav_user.email, token),
        'X-Mailu-Auth-Context': 'webdav', 'X-Forwarded-By': '192.168.203.10',
    }).status_code == 401


def test_shared_auth_endpoint_requires_nginx_context_for_cookies(client, dav_user):
    headers = {'X-Mailu-Original-Method': 'GET', 'Sec-Fetch-Site': 'same-origin'}
    assert client.get('/internal/auth/basic', headers=headers).status_code == 401
    assert client.get('/internal/auth/basic', headers={
        **headers, 'X-Mailu-Auth-Context': 'webdav',
    }).status_code == 200
    assert client.get('/internal/auth/webdav').status_code == 404
    assert client.get('/internal/auth/webdav-webmail').status_code == 404


def test_malformed_password_is_rejected(client, dav_user):
    value = base64.b64encode(dav_user.email.encode() + b':\xff').decode()
    assert client.get('/internal/auth/basic', headers={
        'Authorization': 'Basic ' + value,
    }).status_code == 401
