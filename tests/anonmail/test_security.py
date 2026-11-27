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
