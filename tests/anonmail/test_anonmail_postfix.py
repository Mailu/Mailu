from mailu import models

TOKEN = 'a'*32


def test_postfix_sees_generated_alias(app, client, create_user_and_token, grant_domain_access):
    with app.app_context():
        # 1. Setup: Create domain, user, token, and grant access
        d = models.Domain(name='example.com', anonmail_enabled=True)
        models.db.session.add(d)
        models.db.session.commit()

        user, token = create_user_and_token()
        grant_domain_access('example.com', user=user)

        
        # 2. Create a random alias via the API
        headers = {'Authorization': f'Bearer {TOKEN}'}
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


def test_postfix_sees_alias_with_multiple_destinations(app, client, create_user_and_token, grant_domain_access):
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

        headers = {'Authorization': f'Bearer {TOKEN}'}
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
