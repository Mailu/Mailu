import os

# Set reduced rate limits at import time so the shared `app` fixture
# will pick them up when creating the app for tests.
os.environ.setdefault('AUTH_RATELIMIT_IP', '2/hour')
os.environ.setdefault('AUTH_RATELIMIT_USER', '5/day')

from mailu import models


def test_rate_limiting_triggers_429_after_retries(app, client, create_user_and_token, grant_domain_access):
    with app.app_context():
        models.db.create_all()
        models.Base.metadata.create_all(bind=models.db.engine)

        d = models.Domain(name='example.com', anonmail_enabled=True)
        models.db.session.add(d)
        models.db.session.commit()

        user, token = create_user_and_token(email='rl@example.com', token_str='d' * 32)
        grant_domain_access('example.com', user=user)

        # Use malformed token to trigger rate-limiter increments (invalid format -> 401)
        headers = {'Authorization': 'Bearer invalid-token-format'}
        rv1 = client.post('/api/alias/random/new', headers=headers, json={})
        assert rv1.status_code in (401, 403)

        rv2 = client.post('/api/alias/random/new', headers=headers, json={})
        # After second bad attempt (limit 2/hour) subsequent attempts should be rate-limited
        rv3 = client.post('/api/alias/random/new', headers=headers, json={})
        assert rv3.status_code == 429
