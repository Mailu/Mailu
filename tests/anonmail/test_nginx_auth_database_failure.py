import sqlalchemy.exc

from mailu import models, utils


AUTH_HEADERS = {
    'Auth-Method': 'plain',
    'Auth-Protocol': 'smtp',
    'Auth-User': 'person@example.com',
    'Auth-Pass': 'invalid-password',
    'Auth-Port': '587',
    'Client-Ip': '192.0.2.1',
    'Client-Port': '12345',
}


def test_database_pool_checks_connections_before_reuse(app):
    assert models.db.engine.pool._pre_ping is True


def test_database_failure_returns_temporary_smtp_error_without_rate_limit(
    app, client, monkeypatch
):
    session_removed = []
    rate_limited = []

    def fail_user_lookup(*args, **kwargs):
        raise sqlalchemy.exc.OperationalError(
            'SELECT user', {}, Exception('database unavailable')
        )

    monkeypatch.setattr(models.db.session, 'get', fail_user_lookup)
    monkeypatch.setattr(
        models.db.session, 'remove', lambda: session_removed.append(True)
    )
    monkeypatch.setattr(utils.limiter, 'should_rate_limit_ip', lambda ip: False)
    monkeypatch.setattr(
        utils.limiter,
        'rate_limit_ip',
        lambda *args, **kwargs: rate_limited.append((args, kwargs)),
    )

    response = client.get('/internal/auth/email', headers=AUTH_HEADERS)

    assert response.headers['Auth-Status'] == 'Temporary authentication failure'
    assert response.headers['Auth-Error-Code'] == '454 4.7.0'
    assert session_removed == [True]
    assert rate_limited == []


def test_unknown_user_still_returns_invalid_credentials(app, client, monkeypatch):
    monkeypatch.setattr(utils.limiter, 'should_rate_limit_ip', lambda ip: False)

    response = client.get('/internal/auth/email', headers=AUTH_HEADERS)

    assert response.headers['Auth-Status'] == 'Authentication credentials invalid'
    assert response.headers['Auth-Error-Code'] == '535 5.7.8'
