from mailu import models


class TestMailboxQuota:
    def test_dovecot_userdb_returns_the_per_user_limit(self, app, client):
        with app.app_context():
            models.db.session.add(models.Domain(name='example.com'))
            user = models.User(localpart='alice', domain_name='example.com', quota_bytes=123456)
            user.dovecot_uid = 100001
            user.set_password('password')
            models.db.session.add(user)
            models.db.session.commit()

            response = client.get('/internal/dovecot/userdb/alice@example.com')

            assert response.status_code == 200
            assert response.get_json()['quota_storage_size'] == '123456'
            assert response.get_json()['home'] == '/mail/./example.com/g2/alice'


class TestDomainStorageQuota:
    def test_unset_domain_limit_defaults_to_unlimited(self, app, client):
        with app.app_context():
            models.db.session.add(models.Domain(name='example.com'))
            models.db.session.commit()
            assert models.db.session.get(models.Domain, 'example.com').max_domain_quota_bytes == 0

            response = client.post('/internal/postfix/domain-quota', json={
                'recipient': 'unknown@example.com', 'size': 1000000,
            })

            assert response.status_code == 200
            assert response.get_json() == {'allowed': True, 'domains': []}

    def test_domain_check_sums_mailbox_usage_and_accounts_for_declared_size(self, app, client):
        with app.app_context():
            domain = models.Domain(name='example.com', max_domain_quota_bytes=100)
            alice = models.User(
                localpart='alice', domain_name='example.com', quota_bytes=100, quota_bytes_used=40,
            )
            bob = models.User(
                localpart='bob', domain_name='example.com', quota_bytes=100, quota_bytes_used=35,
            )
            alice.set_password('password')
            bob.set_password('password')
            models.db.session.add_all((domain, alice, bob))
            models.db.session.commit()
            assert domain.max_domain_quota_bytes == 100
            assert client.post(
                '/internal/dovecot/quota/storage/alice@example.com', json=40,
            ).status_code == 200
            assert client.post(
                '/internal/dovecot/quota/storage/bob@example.com', json=35,
            ).status_code == 200

            allowed = client.post('/internal/postfix/domain-quota', json={
                'recipient': 'alice@example.com', 'size': 25,
            })
            over = client.post('/internal/postfix/domain-quota', json={
                'recipient': 'alice@example.com', 'size': 26,
            })

            assert allowed.status_code == 200
            assert allowed.get_json() == {
                'allowed': True,
                'domains': [{'domain': 'example.com', 'used': 75, 'limit': 100, 'allowed': True}],
            }
            assert over.get_json()['allowed'] is False

    def test_domain_check_follows_alias_to_mailbox_domain(self, app, client):
        with app.app_context():
            domain = models.Domain(name='example.com', max_domain_quota_bytes=100)
            user = models.User(
                localpart='alice', domain_name='example.com', quota_bytes_used=100,
            )
            user.set_password('password')
            alias = models.Alias(
                localpart='sales', domain_name='example.com', destination=['alice@example.com'],
            )
            models.db.session.add_all((domain, user, alias))
            models.db.session.commit()

            response = client.post('/internal/postfix/domain-quota', json={
                'recipient': 'sales@example.com', 'size': 1,
            })

            assert response.status_code == 200
            assert response.get_json()['allowed'] is False

    def test_domain_edit_shows_and_saves_aggregate_limit(self, app, client):
        app.config['WTF_CSRF_ENABLED'] = False
        with app.app_context():
            domain = models.Domain(name='example.com', max_domain_quota_bytes=1000)
            admin = models.User(localpart='admin', domain_name='example.com', global_admin=True)
            admin.set_password('password')
            models.db.session.add_all((domain, admin))
            models.db.session.commit()

            with client.session_transaction() as session:
                session['_user_id'] = admin.email
                session['_fresh'] = True

            path = app.config['WEB_ADMIN'] + '/domain/edit/example.com'
            page = client.get(path)
            assert page.status_code == 200
            assert b'name="max_domain_quota_bytes"' in page.data

            response = client.post(path, data={
                'name': 'example.com',
                'max_users': '-1',
                'max_aliases': '-1',
                'max_quota_bytes': '500',
                'max_domain_quota_bytes': '2000',
                'passkey_aaguid_mode': 'allow',
                'passkey_backup_eligible_policy': 'optional',
                'passkey_backup_state_policy': 'optional',
                'passkey_attestation_policy': 'optional',
                'passkey_resident_key': 'preferred',
            })

            assert response.status_code == 302
            assert models.db.session.get(models.Domain, 'example.com').max_domain_quota_bytes == 2000
