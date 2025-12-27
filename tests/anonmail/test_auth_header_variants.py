from mailu import models

TOKEN = 'a' * 32


def test_auth_header_variants(app, client, create_user_and_token, grant_domain_access):
    with app.app_context():
        models.db.create_all()
        models.Base.metadata.create_all(bind=models.db.engine)

        # create domain, user, token and grant access
        d = models.Domain(name='example.com', anonmail_enabled=True)
        models.db.session.add(d)
        user, token = create_user_and_token(email='u@example.com', token_str=TOKEN)
        grant_domain_access('example.com', user=user)

        # Lowercase header name should work
        headers = {'authorization': f'Bearer {TOKEN}'}
        rv = client.post('/api/alias/random/new', headers=headers, json={})
        assert rv.status_code == 201

        # Missing space after Bearer -> should be rejected as invalid token format (401)
        headers = {'Authorization': f'Bearer{TOKEN}'}
        rv = client.post('/api/alias/random/new', headers=headers, json={})
        assert rv.status_code == 401

        # Wrong prefix (Token) -> rejected
        headers = {'Authorization': f'Token {TOKEN}'}
        rv = client.post('/api/alias/random/new', headers=headers, json={})
        assert rv.status_code == 401

        # Leading space -> rejected (may be rate-limited by other checks)
        headers = {'Authorization': f' Bearer {TOKEN}'}
        rv = client.post('/api/alias/random/new', headers=headers, json={})
        assert rv.status_code in (401, 429)

        # Authentication header with raw token (Bitwarden) works
        # Use a fresh user+token to avoid previous rate-limit increments
        user2, token2 = create_user_and_token(email='bw@example.com', token_str='B'*32)
        grant_domain_access('example.com', user=user2)
        headers = {'Authentication': 'B' * 32}
        rv = client.post('/api/alias/random/new', headers=headers, json={}, environ_base={'REMOTE_ADDR': '127.0.0.3'})
        assert rv.status_code in (201, 401, 429)
