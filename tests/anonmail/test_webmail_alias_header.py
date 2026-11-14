from mailu import models


def _sign_in(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = user.get_id()
        session['_fresh'] = True


def test_webmail_auth_returns_only_active_sender_aliases(app, client):
    with app.app_context():
        domain = models.Domain(name='example.com')
        models.db.session.add(domain)
        models.db.session.commit()

        user = models.User(localpart='alice', domain_name='example.com')
        disabled_owner = models.User(localpart='disabled', domain_name='example.com', enabled=False)
        user.set_password('password')
        disabled_owner.set_password('password')
        models.db.session.add_all([user, disabled_owner])
        models.db.session.commit()

        aliases = [
            models.Alias(
                localpart='sender', domain_name='example.com',
                destination=[user.email],
            ),
            models.Alias(
                localpart='disabled-alias', domain_name='example.com',
                destination=[user.email], disabled=True,
            ),
            models.Alias(
                localpart='wildcard', domain_name='example.com',
                destination=[user.email], wildcard=True,
            ),
            models.Alias(
                localpart='inactive-owner', domain_name='example.com',
                destination=[user.email], owner_email=disabled_owner.email,
            ),
            models.Alias(
                localpart='other', domain_name='example.com',
                destination=['bob@example.com'],
            ),
            models.Alias(
                localpart='substring', domain_name='example.com',
                destination=['xalice@example.com'],
            ),
        ]
        models.db.session.add_all(aliases)
        models.db.session.commit()
        expected_email = aliases[0].email

        _sign_in(client, user)

        response = client.get(
            '/internal/auth/user',
            headers={'X-Mailu-Original-URI': '/webmail/sso.php'},
        )
        assert response.status_code == 200
        assert response.headers['X-User-Aliases'] == expected_email
        assert response.headers['X-User-Aliases-Complete'] == 'true'

        # Normal auth checks must not calculate or return the alias list.
        ordinary_response = client.get('/internal/auth/user')
        assert ordinary_response.status_code == 200
        assert 'X-User-Aliases' not in ordinary_response.headers


def test_webmail_auth_marks_oversized_alias_header_incomplete(app, client):
    with app.app_context():
        domain = models.Domain(name='example.com')
        models.db.session.add(domain)
        models.db.session.commit()

        user = models.User(localpart='alice', domain_name='example.com')
        user.set_password('password')
        models.db.session.add(user)
        models.db.session.commit()

        models.db.session.add_all([
            models.Alias(
                localpart=f'alias-{index:03}', domain_name='example.com',
                destination=[user.email],
            )
            for index in range(110)
        ])
        models.db.session.commit()
        _sign_in(client, user)

        response = client.get(
            '/internal/auth/user',
            headers={'X-Mailu-Original-URI': '/webmail/sso.php'},
        )
        assert response.status_code == 200
        assert 'X-User-Aliases' not in response.headers
        assert response.headers['X-User-Aliases-Complete'] == 'false'
