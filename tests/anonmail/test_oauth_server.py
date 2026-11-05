import base64
import hashlib
import logging
import re
from urllib.parse import parse_qs, urlsplit

from mailu import models


def pkce_pair():
    verifier = 'k' * 43
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b'=').decode()
    return verifier, challenge


def csrf_token(response):
    return re.search(
        rb'name="csrf_token"[^>]*value="([^"]+)"', response.data,
    ).group(1).decode()


def sign_in_test_user(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = user.email
        session['_fresh'] = True


def test_mailu_issues_pkce_tokens_and_supports_refresh_and_revocation(app, client, create_user_and_token, caplog):
    caplog.set_level(logging.INFO)
    app.config.update(
        HOSTNAME='mail.example.org',
        TLS_FLAVOR='cert',
        OAUTH2_REFRESH_TOKEN_TTL=14 * 24 * 3600,
        WTF_CSRF_ENABLED=True,
    )
    user, _ = create_user_and_token(email='oauth@example.org')
    sign_in_test_user(client, user)
    verifier, challenge = pkce_pair()
    redirect_uri = 'http://127.0.0.1:49152/'
    authorization = {
        'client_id': 'mailu',
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'scope': 'imap smtp offline_access',
        'state': 'test-state',
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    }

    response = client.get('/admin/oauth2/authorize', query_string=authorization)
    assert response.status_code == 200
    assert user.email.encode() in response.data
    form_data = dict(
        authorization,
        csrf_token=csrf_token(response),
        selected_scopes=['imap', 'smtp', 'offline_access'],
        approve='Allow access',
    )
    response = client.post('/admin/oauth2/authorize', data=form_data)
    assert response.status_code == 302
    callback = urlsplit(response.headers['Location'])
    params = parse_qs(callback.query)
    assert callback.scheme == 'http'
    assert callback.hostname == '127.0.0.1'
    assert params['state'] == ['test-state']
    code = params['code'][0]

    response = client.post('/admin/oauth2/token', data={
        'grant_type': 'authorization_code',
        'client_id': 'mailu',
        'code': code,
        'redirect_uri': redirect_uri,
        'code_verifier': verifier,
    })
    assert response.status_code == 200
    tokens = response.get_json()
    assert tokens['expires_in'] == 24 * 3600
    assert tokens['scope'] == 'imap offline_access smtp'
    assert tokens['token_type'] == 'Bearer'

    grant = models.OAuth2Grant.query.one()
    assert grant.refresh_expires_at - grant.access_expires_at == 14 * 24 * 3600 - 24 * 3600
    assert tokens['access_token'] not in grant.access_token_hash

    response = client.post('/internal/oauth2/introspect', data={'token': tokens['access_token']})
    assert response.get_json()['active'] is True
    assert response.get_json()['email'] == user.email
    assert response.get_json()['scope'] == tokens['scope']
    assert client.get('/admin/oauth2/tokens').status_code == 200
    assert client.post(
        '/internal/oauth2/introspect', data={'token': tokens['access_token']},
        headers={'X-Dovecot-Auth-Protocol': 'pop3'},
    ).get_json() == {'active': False}
    user.enable_imap = False
    models.db.session.commit()
    assert client.post(
        '/internal/oauth2/introspect', data={'token': tokens['access_token']},
        headers={'X-Dovecot-Auth-Protocol': 'imap'},
    ).get_json() == {'active': False}
    user.enable_imap = True
    models.db.session.commit()

    response = client.post('/admin/oauth2/token', data={
        'grant_type': 'refresh_token',
        'client_id': 'mailu',
        'refresh_token': tokens['refresh_token'],
    })
    assert response.status_code == 200
    refreshed = response.get_json()
    assert refreshed['access_token'] != tokens['access_token']
    assert refreshed['refresh_token'] != tokens['refresh_token']
    assert client.post('/internal/oauth2/introspect', data={
        'token': tokens['access_token'],
    }).get_json() == {'active': False}

    response = client.post('/admin/oauth2/revoke', data={
        'client_id': 'mailu', 'token': refreshed['refresh_token'],
    })
    assert response.status_code == 200
    assert client.post('/internal/oauth2/introspect', data={
        'token': refreshed['access_token'],
    }).get_json() == {'active': False}
    assert 'OAuth tokens issued' in caplog.text
    assert 'OAuth tokens refreshed and rotated' in caplog.text
    assert 'OAuth grant revoked' in caplog.text
    for secret in (code, tokens['access_token'], tokens['refresh_token'], refreshed['access_token'], refreshed['refresh_token']):
        assert secret not in caplog.text


def test_mailu_requires_registered_loopback_redirect_and_s256(app, client, create_user_and_token):
    app.config.update(HOSTNAME='mail.example.org', TLS_FLAVOR='cert')
    user, _ = create_user_and_token(email='oauth@example.org')
    sign_in_test_user(client, user)
    _, challenge = pkce_pair()
    response = client.get('/admin/oauth2/authorize', query_string={
        'client_id': 'mailu',
        'response_type': 'code',
        'redirect_uri': 'https://attacker.example/steal',
        'scope': 'imap smtp offline_access',
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    })
    assert response.status_code == 400

    response = client.get('/admin/oauth2/authorize', query_string={
        'client_id': 'mailu',
        'response_type': 'code',
        'redirect_uri': 'http://localhost/',
        'scope': 'imap smtp offline_access',
        'code_challenge': challenge,
        'code_challenge_method': 'plain',
    })
    assert response.status_code == 302
    assert parse_qs(urlsplit(response.headers['Location']).query)['error'] == ['invalid_request']


def test_oauth_authorization_returns_to_the_request_after_mailu_login(app, client):
    _, challenge = pkce_pair()
    authorization = {
        'client_id': 'mailu',
        'response_type': 'code',
        'redirect_uri': 'http://127.0.0.1/',
        'scope': 'imap smtp offline_access',
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    }
    response = client.get('/admin/oauth2/authorize', query_string=authorization)
    assert response.status_code == 302
    assert urlsplit(response.headers['Location']).path == '/sso/login'
    with client.session_transaction() as session:
        assert session['signin_destination']['path'].startswith('/admin/oauth2/authorize?')


def test_mailu_publishes_authorization_server_metadata(app, client):
    app.config.update(
        HOSTNAME='mail.example.org',
        TLS_FLAVOR='cert',
        WEB_ADMIN='/admin',
    )
    response = client.get('/.well-known/oauth-authorization-server')
    metadata = response.get_json()
    assert response.status_code == 200
    assert metadata['issuer'] == 'https://mail.example.org'
    assert metadata['authorization_endpoint'] == 'https://mail.example.org/admin/oauth2/authorize'
    assert metadata['token_endpoint'] == 'https://mail.example.org/admin/oauth2/token'
    assert metadata['code_challenge_methods_supported'] == ['S256']
