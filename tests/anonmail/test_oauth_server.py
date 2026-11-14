import base64
import hashlib
import logging
import re
import time
from urllib.parse import parse_qs, urlsplit

from mailu import models, oauth2


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
            OAUTH2_ACCESS_TOKEN_TTL=300,
        OAUTH2_REFRESH_TOKEN_TTL=14 * 24 * 3600,
            OAUTH2_REFRESH_TOKEN_IDLE=600,
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
    assert tokens['expires_in'] == 300
    assert tokens['scope'] == 'imap offline_access smtp'
    assert tokens['token_type'] == 'Bearer'

    grant = models.OAuth2Grant.query.one()
    assert re.fullmatch(r'[A-Za-z0-9_-]{22}', grant.grant_id)
    assert oauth2._parse_mail_token(tokens['access_token'], 'access') == (
        'access', grant.grant_id, 0,
    )
    assert oauth2._parse_mail_token(tokens['refresh_token'], 'refresh') == (
        'refresh', grant.grant_id, 0,
    )
    assert oauth2._parse_mail_token(
        oauth2._derive_mail_token('refresh', 'a' * 32, 0), 'refresh',
    ) is None
    assert grant.access_expires_at <= grant.last_refresh_at + 600
    assert grant.token_generation == 0

    # OAuth signing is backed by its own persistent key, not Flask SECRET_KEY.
    app.config['SECRET_KEY'] = 'rotated-secret-key'
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

    # Near the absolute refresh expiry, the next access token is capped too.
    grant.refresh_expires_at = int(time.time()) + 120
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
    assert grant.token_generation == 1
    assert 0 < refreshed['expires_in'] <= 120
    assert grant.access_expires_at <= grant.refresh_expires_at
    assert client.post('/internal/oauth2/introspect', data={
        'token': tokens['access_token'],
    }).get_json() == {'active': False}

    response = client.post('/admin/oauth2/token', data={
        'grant_type': 'refresh_token', 'client_id': 'mailu',
        'refresh_token': tokens['refresh_token'],
    })
    assert response.status_code == 400
    assert response.get_json()['error'] == 'invalid_grant'
    assert models.OAuth2Grant.query.count() == 0
    assert client.post('/internal/oauth2/introspect', data={
        'token': refreshed['access_token'],
    }).get_json() == {'active': False}
    assert 'OAuth tokens issued' in caplog.text
    assert 'OAuth tokens refreshed and rotated' in caplog.text
    assert 'OAuth refresh token replay detected' in caplog.text
    assert grant.grant_id in caplog.text
    for secret in (code, tokens['access_token'], tokens['refresh_token'], refreshed['access_token'], refreshed['refresh_token']):
        assert secret not in caplog.text


def test_deleted_grant_identifier_is_not_reused(app, create_user_and_token):
    user, _ = create_user_and_token(email='grant-id@example.org')
    app.config['OAUTH2_ACCESS_TOKEN_TTL'] = 300
    with app.test_request_context(headers={'User-Agent': 'Thunderbird/161.0'}):
        first = oauth2._issue_tokens(user.email, 'mailu', 'imap offline_access')
        first_grant = models.OAuth2Grant.query.one()
        first_id = first_grant.grant_id
        first_token = first['refresh_token']
        models.db.session.delete(first_grant)
        models.db.session.commit()

        second = oauth2._issue_tokens(user.email, 'mailu', 'imap offline_access')
        second_grant = models.OAuth2Grant.query.one()

    assert second_grant.grant_id != first_id
    assert second['refresh_token'] != first_token
    assert oauth2._parse_mail_token(first_token, 'refresh') == (
        'refresh', first_id, 0,
    )
    assert oauth2._parse_mail_token(second['refresh_token'], 'refresh') == (
        'refresh', second_grant.grant_id, 0,
    )


def test_oauth_cleanup_removes_expired_codes_and_retains_recently_expired_grants(
    app, create_user_and_token,
):
    user, _ = create_user_and_token(email='cleanup@example.org')
    now = int(time.time())
    old_expiry = now - oauth2.EXPIRED_GRANT_RETENTION - 1
    models.db.session.add_all([
        models.OAuth2AuthorizationCode(
            code_hash='a' * 64, user=user, client_id='mailu',
            redirect_uri='http://127.0.0.1:12345/', scope='imap',
            code_challenge='b' * 43, expires_at=now - 1,
        ),
        models.OAuth2AuthorizationCode(
            code_hash='c' * 64, user=user, client_id='mailu',
            redirect_uri='http://127.0.0.1:12345/', scope='imap',
            code_challenge='d' * 43, expires_at=now + 600,
        ),
        models.OAuth2Grant(
            user=user, client_id='mailu', scope='imap',
            access_expires_at=old_expiry, refresh_expires_at=None,
            client_name='Expired app', last_refresh_at=None,
        ),
        models.OAuth2Grant(
            user=user, client_id='mailu', scope='imap offline_access',
            access_expires_at=old_expiry, refresh_expires_at=old_expiry,
            client_name='Old app', last_refresh_at=old_expiry,
        ),
        models.OAuth2Grant(
            user=user, client_id='mailu', scope='imap offline_access',
            access_expires_at=now - 1, refresh_expires_at=now - 1,
            client_name='Recently expired app', last_refresh_at=now - 1,
        ),
        models.OAuth2Grant(
            user=user, client_id='mailu', scope='imap offline_access',
            access_expires_at=now - 1, refresh_expires_at=now + 3600,
            client_name='Active app', last_refresh_at=now,
        ),
    ])
    models.db.session.commit()

    removed_codes, removed_grants = oauth2.cleanup_expired_records(now)

    assert removed_codes == 1
    assert removed_grants == 2
    assert models.OAuth2AuthorizationCode.query.count() == 1
    assert models.OAuth2Grant.query.count() == 2


def test_redirect_uri_has_an_explicit_maximum_length():
    assert not oauth2._valid_redirect_uri('http://127.0.0.1/' + 'x' * 2049)


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
    login_page = client.get(response.headers['Location'])
    assert b'you will be redirected to approve this mail app' in login_page.data.lower()
    with client.session_transaction() as session:
        assert session['signin_destination']['path'].startswith('/admin/oauth2/authorize?')


def test_mailu_publishes_authorization_server_metadata(app, client):
    app.config.update(
        HOSTNAME='mail.example.org',
        HOSTNAMES='mail.example.org,alias.example.org',
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

    alias_response = client.get(
        '/.well-known/oauth-authorization-server',
        base_url='https://alias.example.org',
    )
    alias_metadata = alias_response.get_json()
    assert alias_metadata['issuer'] == 'https://alias.example.org'
    assert alias_metadata['authorization_endpoint'] == 'https://alias.example.org/admin/oauth2/authorize'
    assert alias_metadata['token_endpoint'] == 'https://alias.example.org/admin/oauth2/token'
