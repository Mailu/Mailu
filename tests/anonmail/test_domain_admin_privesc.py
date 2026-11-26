"""Regression tests for #2685 -- a domain manager must not be able to take over
an account that outranks them.

``access.domain_admin`` (user_edit, user_password) and ``access.owner``
(token_create) authorize purely on the *target's* domain: ``domain in
current_user.get_managed_domains()``. With no rank check, a manager of a domain
can reset the password of -- or mint an API token for -- a global admin (or a
manager of another domain) who merely owns a mailbox in the managed domain,
taking over that privileged account.

These tests exercise the authorization decorators via GET (the decorator runs
before the view body): 200 == access granted, 403 == denied. Without the fix the
403 cases return 200.
"""

from mailu import models


class TestDomainAdminPrivesc:

    @staticmethod
    def _login(client, user):
        with client.session_transaction() as sess:
            sess['_user_id'] = user.get_id()
            sess['_auth_generation'] = user.auth_generation
            sess['_fresh'] = True

    @staticmethod
    def _user(localpart, domain_name, *, global_admin=False, manages=()):
        user = models.User(localpart=localpart, domain_name=domain_name)
        user.set_password('password')
        user.global_admin = global_admin
        models.db.session.add(user)
        models.db.session.commit()
        for dom in manages:
            dom.managers.append(user)
        models.db.session.commit()
        return user

    def _setup(self):
        example = models.Domain(name='example.com')
        other = models.Domain(name='other.com')
        models.db.session.add_all([example, other])
        models.db.session.commit()
        return {
            'example': example,
            'other': other,
            # manager of example.com
            'mgr': self._user('mgr', 'example.com', manages=[example]),
            # global admin who happens to own a mailbox in example.com
            'admin': self._user('admin', 'example.com', global_admin=True),
            # plain mailbox in example.com (subordinate)
            'plain': self._user('plain', 'example.com'),
            # manager of another domain, but owns a mailbox in example.com
            'othermgr': self._user('othermgr', 'example.com', manages=[other]),
        }

    def _get(self, app, client, path):
        prefix = app.config['WEB_ADMIN']
        return client.get(f'{prefix}{path}').status_code

    # --- privesc must be denied (403) -----------------------------------

    def test_manager_cannot_reset_global_admin_password(self, app, client):
        with app.app_context():
            u = self._setup()
            self._login(client, u['mgr'])
            assert self._get(app, client, '/user/password/admin@example.com') == 403

    def test_manager_cannot_edit_global_admin(self, app, client):
        with app.app_context():
            u = self._setup()
            self._login(client, u['mgr'])
            assert self._get(app, client, '/user/edit/admin@example.com') == 403

    def test_manager_cannot_create_token_for_global_admin(self, app, client):
        with app.app_context():
            u = self._setup()
            self._login(client, u['mgr'])
            assert self._get(app, client, '/token/create/admin@example.com') == 403

    def test_manager_cannot_reset_other_domain_manager_password(self, app, client):
        with app.app_context():
            u = self._setup()
            self._login(client, u['mgr'])
            assert self._get(app, client, '/user/password/othermgr@example.com') == 403

    # --- legitimate management must keep working (no regression) ---------

    def test_manager_can_reset_subordinate_password(self, app, client):
        with app.app_context():
            u = self._setup()
            self._login(client, u['mgr'])
            assert self._get(app, client, '/user/password/plain@example.com') == 200

    def test_manager_can_edit_subordinate(self, app, client):
        with app.app_context():
            u = self._setup()
            self._login(client, u['mgr'])
            assert self._get(app, client, '/user/edit/plain@example.com') == 200

    def test_global_admin_can_reset_manager_password(self, app, client):
        with app.app_context():
            u = self._setup()
            self._login(client, u['admin'])
            assert self._get(app, client, '/user/password/mgr@example.com') == 200

    def test_user_can_create_own_token(self, app, client):
        with app.app_context():
            u = self._setup()
            self._login(client, u['mgr'])
            assert self._get(app, client, '/token/create/mgr@example.com') == 200
