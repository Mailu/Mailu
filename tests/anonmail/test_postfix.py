from urllib.parse import quote

from mailu import models


class TestAnonmailPostfixIntegration:
    """Tests for Postfix integration with anonmail aliases"""

    def test_postfix_double_at_does_not_500(self, app, client):
        """ Regression for #3252.

        A lookup key with more than one ``@`` (or a quoted local part) is not a
        valid Mailu address. The internal postfix endpoints must never answer it
        with an unhandled 500: a 500 makes Postfix treat the lookup as a
        temporary failure and retry, which trips the sender's rate limit.

        The two resolve-path endpoints (``alias``, ``sender/login``) answer 404
        via ``_unsupported_address`` — binding such a key in
        ``resolve_destination`` would otherwise raise in ``IdnaEmail``. The two
        SRS endpoints need no guard once srslib >= 0.1.5 handles the extra
        ``@``: ``recipient/map`` is not an SRS address so it answers 404, and
        ``sender/map`` SRS-forwards an external sender (200) or answers 404 for
        a local domain — never 500.
        """
        with app.app_context():
            models.db.session.add(models.Domain(name='example.com'))
            models.db.session.commit()
            for bad in ('a@b@example.com', '"a@b"@example.com'):
                key = quote(bad, safe='')
                for endpoint in ('alias', 'recipient/map', 'sender/login'):
                    rv = client.get(f'/internal/postfix/{endpoint}/{key}')
                    assert rv.status_code == 404, \
                        f'/internal/postfix/{endpoint}/ for {bad!r} -> {rv.status_code}'
            # sender/map: 404 for a local domain, 200 (SRS-forwarded) for an
            # external one — the point is that neither path 500s.
            local = quote('a@b@example.com', safe='')
            external = quote('a@b@external.invalid', safe='')
            assert client.get(f'/internal/postfix/sender/map/{local}').status_code == 404
            assert client.get(f'/internal/postfix/sender/map/{external}').status_code == 200

    def test_postfix_sees_generated_alias(self, app, client, create_user_and_token, grant_domain_access):
        with app.app_context():
            # 1. Setup: Create domain, user, token, and grant access
            d = models.Domain(name='example.com', anonmail_enabled=True)
            models.db.session.add(d)
            models.db.session.commit()

            user, token = create_user_and_token()
            grant_domain_access('example.com', user=user)

            
            # 2. Create a random alias via the API
            headers = {'Authentication': f'{user.email}:{"a" * 32}'}
            payload = {
                'domain': 'example.com', 
                'hostname': 'testsite.com',
                'destination': [user.email]
            }
            rv = client.post('/api/alias/random/new', json=payload, headers=headers)
            assert rv.status_code == 201
            alias_email = rv.get_json()['email']

            # 3. Validate that Postfix internal endpoint sees the alias
            # The internal endpoint is /internal/postfix/alias/<alias>
            rv_postfix = client.get(f'/internal/postfix/alias/{alias_email}')
            assert rv_postfix.status_code == 200
            destinations = rv_postfix.get_json()
            # Postfix expects a comma-separated string of destinations
            assert user.email in destinations

            # 4. Disable the alias and verify Postfix no longer sees it
            # We can use the PATCH /api/v1/alias/me/<alias> endpoint to disable it
            patch_payload = {'disabled': True}
            # disable using the global API token (the /me endpoints require API token auth)
            headers_api = {'Authorization': f'Bearer {app.config["API_TOKEN"]}'}
            rv_patch = client.patch(f'/api/v1/alias/me/{alias_email}', json=patch_payload, headers=headers_api)
            assert rv_patch.status_code == 200

            # Now Postfix should get a 404 for this alias
            rv_postfix_disabled = client.get(f'/internal/postfix/alias/{alias_email}')
            assert rv_postfix_disabled.status_code == 404

    def test_postfix_sender_login_spoofing_is_scoped_to_own_domain(self, app, client):
        """ Regression for #2686.

        ``allow_spoofing`` lets a user authenticate as other senders, but it must
        only apply within that user's own domain. Otherwise a domain manager can
        grant themselves ``allow_spoofing`` and send mail spoofing senders on
        domains they do not manage. The /postfix/sender/login lookup therefore
        only returns a spoofing user for senders in that user's domain.
        """
        with app.app_context():
            models.db.session.add(models.Domain(name='attacker.com'))
            models.db.session.add(models.Domain(name='victim.com'))

            spoofer = models.User(localpart='spoofer', domain_name='attacker.com',
                                  allow_spoofing=True)
            spoofer.set_password('password')
            coworker = models.User(localpart='coworker', domain_name='attacker.com')
            coworker.set_password('password')
            victim = models.User(localpart='victim', domain_name='victim.com')
            victim.set_password('password')
            models.db.session.add_all([spoofer, coworker, victim])
            models.db.session.commit()

            def logins_for(sender):
                rv = client.get(f'/internal/postfix/sender/login/{sender}')
                assert rv.status_code == 200, f'{sender} -> {rv.status_code}'
                return set(rv.get_json().split(','))

            # Same domain: the spoofer may still send as a coworker.
            assert 'spoofer@attacker.com' in logins_for('coworker@attacker.com')

            # Cross domain: the spoofer must NOT be a valid login for the victim.
            assert 'spoofer@attacker.com' not in logins_for('victim@victim.com')

    def test_postfix_sees_alias_with_multiple_destinations(self, app, client, create_user_and_token, grant_domain_access):
        with app.app_context():
            d = models.Domain(name='example.com', anonmail_enabled=True)
            models.db.session.add(d)
            models.db.session.commit()

            user1, token = create_user_and_token(email='user1@example.com')
            user2 = models.User(localpart='user2', domain_name='example.com')
            user2.set_password('password')
            models.db.session.add(user2)
            models.db.session.commit()
            
            grant_domain_access('example.com', user=user1)

            headers = {'Authentication': f'{user1.email}:{"a" * 32}'}
            payload = {}
            rv = client.post('/api/alias/random/new', json=payload, headers=headers)
            assert rv.status_code == 201
            alias_email = rv.get_json()['email']
            
            # Manually update the alias to have multiple destinations
            alias_obj = models.Alias.query.filter_by(email=alias_email).first()
            alias_obj.destination = [user1.email, user2.email]
            models.db.session.commit()

            rv_postfix = client.get(f'/internal/postfix/alias/{alias_email}')
            assert rv_postfix.status_code == 200
            destinations = rv_postfix.get_json()
            assert user1.email in destinations
            assert user2.email in destinations
            assert ',' in destinations
