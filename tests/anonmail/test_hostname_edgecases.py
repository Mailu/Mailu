from mailu import models

TOKEN = 'b' * 32


def test_hostname_edge_cases(app, client, create_user_and_token, grant_domain_access):
    with app.app_context():
        d = models.Domain(name='example.com', anonmail_enabled=True)
        models.db.session.add(d)
        models.db.session.commit()

        user, token = create_user_and_token(email='hosttest@example.com', token_str=TOKEN)
        grant_domain_access('example.com', user=user)

        headers = {'Authentication': f'hosttest@example.com:{TOKEN}'}

        test_cases = [
            ('example.com:8080', 'example'),
            ('sub_domain.example.org', 'example'),
            ('-dash.example.com', 'example'),
            ('localhost', None),  # localhost can't be parsed by tld, falls back to random token
            ('http://user:pass@www.test-site.co.uk:8443/path', 'testsite'),  # test-site domain with dashes removed
        ]

        for hostname, expected_prefix in test_cases:
            rv = client.post(f'/api/alias/random/new?hostname={hostname}', headers=headers, json={})
            assert rv.status_code == 201, f'hostname {hostname} failed: {rv.get_data(as_text=True)}'
            email = rv.get_json()['email']
            localpart = email.split('@', 1)[0]
            if expected_prefix:
                assert localpart.startswith(f'{expected_prefix}.'), f'Expected prefix {expected_prefix} for {hostname}, got {localpart}'
            else:
                # For unparseable hostnames like localhost, should be a random token
                assert len(localpart) > 8, f'Expected random token for {hostname}, got {localpart}'
