"""Unit tests for the alias-login feature.
"""

import base64

from mailu import models
from mailu.internal import nginx


def _setup_alias_test_data(app):
    """Set up test domain, users, and aliases."""
    domain = models.Domain(name='example.com')
    models.db.session.add(domain)

    # Destination user
    user = models.User(localpart='joe', domain_name='example.com', email='joe@example.com')
    user.set_password('secret123')
    models.db.session.add(user)

    # Disabled user
    disabled_user = models.User(
        localpart='inactive', domain_name='example.com', email='inactive@example.com', enabled=False
    )
    disabled_user.set_password('secret123')
    models.db.session.add(disabled_user)

    # Global admin user
    admin_user = models.User(localpart='admin', domain_name='example.com', email='admin@example.com', global_admin=True)
    admin_user.set_password('adminpass')
    models.db.session.add(admin_user)

    # Enabled login alias
    alias_login = models.Alias(
        localpart='joe-alias',
        domain_name='example.com',
        email='joe-alias@example.com',
        destination=['joe@example.com'],
        wildcard=False,
        allow_login=True
    )
    models.db.session.add(alias_login)

    # Standard alias (login not allowed)
    alias_standard = models.Alias(
        localpart='joe-standard',
        domain_name='example.com',
        email='joe-standard@example.com',
        destination=['joe@example.com'],
        wildcard=False,
        allow_login=False
    )
    models.db.session.add(alias_standard)

    # Wildcard alias with allow_login=True (should be rejected/ignored)
    alias_wildcard = models.Alias(
        localpart='wild%',
        domain_name='example.com',
        email='wild%@example.com',
        destination=['joe@example.com'],
        wildcard=True,
        allow_login=True
    )
    models.db.session.add(alias_wildcard)

    # Multi-destination alias with allow_login=True (should be rejected/ignored)
    alias_multi = models.Alias(
        localpart='multi',
        domain_name='example.com',
        email='multi@example.com',
        destination=['joe@example.com', 'admin@example.com'],
        wildcard=False,
        allow_login=True
    )
    models.db.session.add(alias_multi)

    # External destination alias with allow_login=True
    alias_ext = models.Alias(
        localpart='ext',
        domain_name='example.com',
        email='ext@example.com',
        destination=['external@gmail.com'],
        wildcard=False,
        allow_login=True
    )
    models.db.session.add(alias_ext)

    # Alias pointing to disabled user
    alias_dis = models.Alias(
        localpart='dis-target',
        domain_name='example.com',
        email='dis-target@example.com',
        destination=['inactive@example.com'],
        wildcard=False,
        allow_login=True
    )
    models.db.session.add(alias_dis)

    # Disabled alias
    alias_disabled = models.Alias(
        localpart='disabled-alias',
        domain_name='example.com',
        email='disabled-alias@example.com',
        destination=['joe@example.com'],
        wildcard=False,
        disabled=True,
        allow_login=True
    )
    models.db.session.add(alias_disabled)

    models.db.session.commit()


class TestAliasLoginResolution:

    def test_direct_mailbox_resolves_without_alias(self, app):
        with app.app_context():
            _setup_alias_test_data(app)
            user, via_alias = models.User.resolve_login('joe@example.com')
            assert user is not None
            assert user.email == 'joe@example.com'
            assert via_alias is None

    def test_enabled_alias_resolves_to_mailbox(self, app):
        with app.app_context():
            _setup_alias_test_data(app)
            user, via_alias = models.User.resolve_login('joe-alias@example.com')
            assert user is not None
            assert user.email == 'joe@example.com'
            assert via_alias == 'joe-alias@example.com'

    def test_unenabled_alias_returns_none(self, app):
        with app.app_context():
            _setup_alias_test_data(app)
            user, via_alias = models.User.resolve_login('joe-standard@example.com')
            assert user is None
            assert via_alias is None

    def test_wildcard_alias_refuses_login(self, app):
        with app.app_context():
            _setup_alias_test_data(app)
            user, via_alias = models.User.resolve_login('wild%@example.com')
            assert user is None
            assert via_alias is None

    def test_multi_destination_alias_refuses_login(self, app):
        with app.app_context():
            _setup_alias_test_data(app)
            user, via_alias = models.User.resolve_login('multi@example.com')
            assert user is None
            assert via_alias is None

    def test_external_destination_alias_refuses_login(self, app):
        with app.app_context():
            _setup_alias_test_data(app)
            user, via_alias = models.User.resolve_login('ext@example.com')
            assert user is None
            assert via_alias is None

    def test_disabled_target_user_refuses_login(self, app):
        with app.app_context():
            _setup_alias_test_data(app)
            user, via_alias = models.User.resolve_login('dis-target@example.com')
            assert user is None
            assert via_alias is None

    def test_disabled_alias_refuses_login(self, app):
        with app.app_context():
            _setup_alias_test_data(app)
            user, via_alias = models.User.resolve_login('disabled-alias@example.com')
            assert user is None
            assert via_alias is None

    def test_unknown_address_returns_none(self, app):
        with app.app_context():
            _setup_alias_test_data(app)
            user, via_alias = models.User.resolve_login('nonexistent@example.com')
            assert user is None
            assert via_alias is None

    def test_alias_logins_for_mailbox(self, app):
        with app.app_context():
            _setup_alias_test_data(app)
            logins = models.Alias.logins_for(['joe@example.com'])
            assert 'joe-alias@example.com' in logins
            assert 'joe-standard@example.com' not in logins
            assert 'wild%@example.com' not in logins
            assert 'multi@example.com' not in logins


class TestAliasLoginValidation:

    def test_login_problem_checks(self, app):
        with app.app_context():
            _setup_alias_test_data(app)
            alias_ok = models.db.session.get(models.Alias, 'joe-alias@example.com')
            assert models.Alias.login_problem(alias_ok) is None

            alias_wild = models.db.session.get(models.Alias, 'wild%@example.com')
            assert 'wildcard' in models.Alias.login_problem(alias_wild).lower()

            alias_multi = models.db.session.get(models.Alias, 'multi@example.com')
            assert 'exactly one destination' in models.Alias.login_problem(alias_multi).lower()

            alias_ext = models.db.session.get(models.Alias, 'ext@example.com')
            assert 'mailbox on this server' in models.Alias.login_problem(alias_ext).lower()

            alias_dis = models.db.session.get(models.Alias, 'dis-target@example.com')
            assert 'disabled' in models.Alias.login_problem(alias_dis).lower()


class TestAliasInternalEndpoints:

    def test_dovecot_passdb_enabled_alias(self, app, client):
        with app.app_context():
            _setup_alias_test_data(app)
            res = client.get('/internal/dovecot/passdb/joe-alias@example.com')
            assert res.status_code == 200
            data = res.get_json()
            assert data.get('nopassword') == 'Y'
            assert data.get('user') == 'joe@example.com'

    def test_dovecot_passdb_unenabled_alias(self, app, client):
        with app.app_context():
            _setup_alias_test_data(app)
            res = client.get('/internal/dovecot/passdb/joe-standard@example.com')
            assert res.status_code == 404

    def test_postfix_sender_login(self, app, client):
        with app.app_context():
            _setup_alias_test_data(app)
            res = client.get('/internal/postfix/sender/login/joe@example.com')
            assert res.status_code == 200
            allowed_senders = res.get_json().split(',')
            assert 'joe@example.com' in allowed_senders
            assert 'joe-alias@example.com' in allowed_senders

    def test_postfix_sender_rate(self, app, client):
        with app.app_context():
            _setup_alias_test_data(app)
            res = client.get('/internal/postfix/sender/rate/joe-alias@example.com')
            assert res.status_code == 404  # under rate limit returns 404 (permit)


class TestAliasAuthentication:

    def test_nginx_auth_success_with_alias(self, app):
        with app.app_context():
            app.config['AUTH_REQUIRE_TOKENS'] = False
            app.config['IMAP_ADDRESS'] = '127.0.0.1'
            _setup_alias_test_data(app)
            headers = {
                'Auth-Method': 'plain',
                'Auth-User': 'joe-alias@example.com',
                'Auth-Pass': 'secret123',
                'Auth-Protocol': 'imap',
                'Auth-Port': '10143',
                'Client-Ip': '127.0.0.1',
                'Client-Port': '54321',
            }
            auth_result = nginx.handle_authentication(headers)
            assert auth_result.get('Auth-Status') == 'OK'
            assert auth_result.get('Auth-User') == 'joe@example.com'

    def test_nginx_auth_failure_with_wrong_password(self, app):
        with app.app_context():
            app.config['AUTH_REQUIRE_TOKENS'] = False
            app.config['IMAP_ADDRESS'] = '127.0.0.1'
            _setup_alias_test_data(app)
            headers = {
                'Auth-Method': 'plain',
                'Auth-User': 'joe-alias@example.com',
                'Auth-Pass': 'wrongpass',
                'Auth-Protocol': 'imap',
                'Auth-Port': '10143',
                'Client-Ip': '127.0.0.1',
                'Client-Port': '54321',
            }
            auth_result = nginx.handle_authentication(headers)
            assert auth_result.get('Auth-Status') != 'OK'

    def test_nginx_auth_failure_with_unticked_alias(self, app):
        with app.app_context():
            app.config['AUTH_REQUIRE_TOKENS'] = False
            app.config['IMAP_ADDRESS'] = '127.0.0.1'
            _setup_alias_test_data(app)
            headers = {
                'Auth-Method': 'plain',
                'Auth-User': 'joe-standard@example.com',
                'Auth-Pass': 'secret123',
                'Auth-Protocol': 'imap',
                'Auth-Port': '10143',
                'Client-Ip': '127.0.0.1',
                'Client-Port': '54321',
            }
            auth_result = nginx.handle_authentication(headers)
            assert auth_result.get('Auth-Status') != 'OK'

    def test_basic_auth_with_alias(self, app, client):
        with app.app_context():
            _setup_alias_test_data(app)
            creds = base64.b64encode(b'joe-alias@example.com:secret123').decode('ascii')
            res = client.get('/internal/auth/basic', headers={'Authorization': f'Basic {creds}'})
            assert res.status_code == 200
            assert res.headers.get('X-User') == 'joe@example.com'


class TestMigrationRoundtrip:

    def test_migration_upgrade_and_downgrade(self, app):
        import importlib.util
        import pathlib
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        import sqlalchemy as sa

        mig_file = (
            pathlib.Path(models.__file__).resolve().parent.parent
            / 'migrations' / 'versions' / 'c29f4a18e72b_alias_allow_login.py'
        )
        spec = importlib.util.spec_from_file_location('mig_alias_login', mig_file)
        mig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig)

        with app.app_context():
            engine = models.db.engine

            # Test downgrade (drops allow_login)
            with engine.begin() as conn:
                ctx = MigrationContext.configure(conn)
                mig.op = Operations(ctx)
                mig.downgrade()

            with engine.connect() as conn:
                insp = sa.inspect(conn)
                cols = [c['name'] for c in insp.get_columns('alias')]
                assert 'allow_login' not in cols

            # Test upgrade (adds allow_login)
            with engine.begin() as conn:
                ctx = MigrationContext.configure(conn)
                mig.op = Operations(ctx)
                mig.upgrade()

            with engine.connect() as conn:
                insp = sa.inspect(conn)
                cols = [c['name'] for c in insp.get_columns('alias')]
                assert 'allow_login' in cols
