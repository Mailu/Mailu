""" Regression tests: internal endpoints that look a user up by a client-supplied
    address must answer malformed input with a clean status, not crash with 500.

    - /internal/auth/basic decoded the Basic credentials without guarding against a
      malformed header (bad base64, or no ':' separator) -> binascii.Error/ValueError
      -> 500. It should fall through to 401.
    - /internal/dovecot/passdb|quota|sieve looked the user up with an unguarded
      db.session.get(); a username that is not a storable e-mail (no '@', or a
      non-IDNA domain) raised a StatementError -> 500. The sibling userdb endpoint
      already caught this and returned 404.
"""

import base64

from mailu import models


def test_basic_auth_invalid_base64_returns_401(app, client):
    with app.app_context():
        rv = client.get('/internal/auth/basic', headers={'Authorization': 'Basic x'})
        assert rv.status_code == 401


def test_basic_auth_missing_colon_returns_401(app, client):
    with app.app_context():
        encoded = base64.b64encode(b'foo').decode()
        rv = client.get('/internal/auth/basic', headers={'Authorization': f'Basic {encoded}'})
        assert rv.status_code == 401


def test_dovecot_passdb_malformed_username_returns_404(app, client):
    with app.app_context():
        # no '@' -> not a storable IdnaEmail -> StatementError on the pk lookup
        assert client.get('/internal/dovecot/passdb/foo').status_code == 404


def test_dovecot_sieve_data_malformed_username_returns_404(app, client):
    with app.app_context():
        assert client.get('/internal/dovecot/sieve/data/default/foo').status_code == 404


def test_dovecot_passdb_unknown_valid_user_still_404(app, client):
    with app.app_context():
        # a well-formed but non-existent address keeps returning a clean 404
        assert client.get('/internal/dovecot/passdb/nobody@example.com').status_code == 404
