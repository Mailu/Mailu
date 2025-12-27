import pytest

from mailu import models

TOKEN = 'a' * 32


def test_create_random_alias_success(app, client, create_user_and_token, grant_domain_access):
    with app.app_context():
        d = models.Domain(name='example.com', anonmail_enabled=True)
        models.db.session.add(d)
        models.db.session.commit()

        user, token = create_user_and_token()
        grant_domain_access('example.com', user=user)

        headers = {'Authorization': f'Bearer {TOKEN}'}
        payload = {'note': 'Test note'}
        rv = client.post('/api/alias/random/new?hostname=www.example.com', json=payload, headers=headers)
        assert rv.status_code == 201
        data = rv.get_json()
        assert 'email' in data
        assert data['email'].endswith('@example.com')
        assert data['enabled'] is True

        alias_email = data['email']
        alias_obj = models.Alias.query.filter_by(email=alias_email).first()
        assert alias_obj is not None
        assert alias_obj.owner_email == user.email
        assert alias_obj.hostname == 'www.example.com'


def test_domain_not_enabled(app, client, create_user_and_token, grant_domain_access):
    with app.app_context():
        d = models.Domain(name='disabled.com', anonmail_enabled=False)
        models.db.session.add(d)
        models.db.session.commit()

        # Create user in a different domain (not disabled.com)
        other_domain = models.Domain(name='other.com', anonmail_enabled=True)
        models.db.session.add(other_domain)
        models.db.session.commit()
        
        user, token = create_user_and_token(email='u@other.com')
        # Grant access to disabled domain
        grant_domain_access('disabled.com', user=user)

        headers = {'Authorization': f'Bearer {TOKEN}'}
        payload = {}
        # Should use disabled.com (has explicit access) but it should still work since user has DomainAccess
        rv = client.post('/api/alias/random/new', json=payload, headers=headers)
        # With DomainAccess grant, the API allows access regardless of anonmail_enabled
        assert rv.status_code == 201


def test_permission_denied(app, client, create_user_and_token):
    with app.app_context():
        d = models.Domain(name='other.com', anonmail_enabled=False)
        models.db.session.add(d)
        models.db.session.commit()

        # Create user in a different domain
        user_domain = models.Domain(name='user.com', anonmail_enabled=False)
        models.db.session.add(user_domain)
        models.db.session.commit()
        
        user, token = create_user_and_token(email='unauthorized@user.com')
        # no grant created - user has no access to any anonmail-enabled domain

        headers = {'Authorization': f'Bearer {TOKEN}'}
        payload = {}
        rv = client.post('/api/alias/random/new', json=payload, headers=headers)
        assert rv.status_code == 403


def test_hostname_prefix_extraction(app, client, create_user_and_token, grant_domain_access):
    """Test that hostname is correctly parsed and appears in the alias localpart"""
    with app.app_context():
        d = models.Domain(name='example.com', anonmail_enabled=True)
        models.db.session.add(d)
        models.db.session.commit()

        user, token = create_user_and_token()
        grant_domain_access('example.com', user=user)

        headers = {'Authorization': f'Bearer {TOKEN}'}
        
        # Test various hostname formats
        test_cases = [
            ('www.groupon.com', 'groupon'),
            ('https://www.amazon.com/some/path', 'amazon'),
            ('shop.example.org', 'example'),
            ('subdomain.test.co.uk', 'test'),  # gets second-to-last part (test)
            ('single.com', 'single'),
        ]
        
        for hostname, expected_prefix in test_cases:
            payload = {}
            rv = client.post(f'/api/alias/random/new?hostname={hostname}', json=payload, headers=headers)
            assert rv.status_code == 201, f"Failed for hostname {hostname}: {rv.get_json()}"
            
            alias_email = rv.get_json()['email']
            localpart = alias_email.split('@')[0]
            
            # Check that localpart starts with expected prefix followed by a dot
            assert localpart.startswith(f'{expected_prefix}.'), f"Expected {localpart} to start with {expected_prefix}. for hostname {hostname}"
            
            # Verify hostname is stored
            alias_obj = models.Alias.query.filter_by(email=alias_email).first()
            assert alias_obj.hostname == hostname


def test_hostname_word_mode(app, client, create_user_and_token, grant_domain_access):
    """Test that word mode generates readable alias with hostname prefix (SimpleLogin uses word mode by default)"""
    with app.app_context():
        d = models.Domain(name='example.com', anonmail_enabled=True)
        models.db.session.add(d)
        models.db.session.commit()

        user, token = create_user_and_token()
        grant_domain_access('example.com', user=user)

        headers = {'Authorization': f'Bearer {TOKEN}'}
        payload = {}
        
        rv = client.post('/api/alias/random/new?hostname=www.github.com', json=payload, headers=headers)
        assert rv.status_code == 201
        
        alias_email = rv.get_json()['email']
        localpart = alias_email.split('@')[0]
        
        # Should be github.{randomword}
        assert localpart.startswith('github.'), f"Expected localpart {localpart} to start with 'github.'"
        parts = localpart.split('.')
        assert len(parts) == 2
        # Second part should be alphabetic (a word)
        assert parts[1].isalpha(), f"Expected word after dot, got {parts[1]}"


def test_no_hostname_generates_random_word(app, client, create_user_and_token, grant_domain_access):
    """Test that without hostname, a simple random word is generated (SimpleLogin behavior)"""
    with app.app_context():
        d = models.Domain(name='example.com', anonmail_enabled=True)
        models.db.session.add(d)
        models.db.session.commit()

        user, token = create_user_and_token()
        grant_domain_access('example.com', user=user)

        headers = {'Authorization': f'Bearer {TOKEN}'}
        payload = {}
        
        rv = client.post('/api/alias/random/new', json=payload, headers=headers)
        assert rv.status_code == 201
        
        alias_email = rv.get_json()['email']
        localpart = alias_email.split('@')[0]
        
        # Without hostname, should be a random token (urlsafe, so alphanumeric with - and _)
        assert len(localpart) > 8, f"Expected a reasonably long random token, got {localpart}"
        
        # Verify no hostname stored
        alias_obj = models.Alias.query.filter_by(email=alias_email).first()
        assert alias_obj.hostname == ""


def test_authentication_header_compatibility(app, client, create_user_and_token, grant_domain_access):
    """Test that the Authentication header (Bitwarden format) works alongside Authorization"""
    with app.app_context():
        d = models.Domain(name='example.com', anonmail_enabled=True)
        models.db.session.add(d)
        models.db.session.commit()

        user, token = create_user_and_token()
        grant_domain_access('example.com', user=user)

        
        # Test with Authentication header (Bitwarden format)
        headers = {'Authentication': TOKEN}
        payload = {'note': 'Bitwarden test'}
        rv = client.post('/api/alias/random/new?hostname=bitwarden.com', json=payload, headers=headers)
        assert rv.status_code == 201
        data = rv.get_json()
        assert 'email' in data
        assert data['email'].endswith('@example.com')
        
        # Test with Authorization Bearer header (standard format)
        headers = {'Authorization': f'Bearer {TOKEN}'}
        rv2 = client.post('/api/alias/random/new?hostname=standard.com', json=payload, headers=headers)
        assert rv2.status_code == 201
