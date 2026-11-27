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
