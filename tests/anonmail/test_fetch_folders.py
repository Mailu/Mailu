"""Regression tests for #4025 — saving a fetch with an empty "Folders" field.

The fetch create/edit views call ``form.populate_obj(fetch)`` (which sets
``fetch.folders`` to the raw *string* from the StringField) and only convert it
to a list when the field is non-empty. With an empty Folders field the value
stays as ``''``, so ``CommaSeparatedList.process_bind_param`` raises
``TypeError('Must be a list of strings')`` on commit -> HTTP 500.
An empty folder list is valid (POP3 ignores it; fetchmail defaults to INBOX).
"""

from mailu import models


class TestFetchEmptyFolders:

    @staticmethod
    def _login(client, user):
        with client.session_transaction() as sess:
            sess['_user_id'] = user.get_id()
            sess['_auth_generation'] = user.auth_generation
            sess['_fresh'] = True

    @staticmethod
    def _make_user():
        models.db.session.add(models.Domain(name='example.com'))
        user = models.User(localpart='u', domain_name='example.com')
        user.set_password('password')
        models.db.session.add(user)
        models.db.session.commit()
        return user

    def test_fetch_edit_with_empty_folders_does_not_500(self, app, client):
        app.config['FETCHMAIL_ENABLED'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        with app.app_context():
            user = self._make_user()
            fetch = models.Fetch(user=user, protocol='pop3', host='mail.example.com',
                                 port=110, username='remote', password='secret',
                                 folders=['INBOX'])
            models.db.session.add(fetch)
            models.db.session.commit()
            fetch_id = fetch.id

            self._login(client, user)
            prefix = app.config['WEB_ADMIN']
            rv = client.post(
                f'{prefix}/fetch/edit/{fetch_id}',
                data={'protocol': 'pop3', 'host': 'mail.example.com', 'port': '110',
                      'username': 'remote', 'password': '', 'folders': '',
                      'submit': 'Submit'},
            )
            assert rv.status_code == 302, f'expected redirect, got {rv.status_code}'
            assert models.Fetch.query.get(fetch_id).folders == []

    def test_fetch_create_with_empty_folders_does_not_500(self, app, client):
        app.config['FETCHMAIL_ENABLED'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        with app.app_context():
            user = self._make_user()
            self._login(client, user)
            prefix = app.config['WEB_ADMIN']
            rv = client.post(
                f'{prefix}/fetch/create/{user.email}',
                data={'protocol': 'pop3', 'host': 'mail.example.com', 'port': '110',
                      'username': 'remote', 'password': 'secret', 'folders': '',
                      'submit': 'Submit'},
            )
            assert rv.status_code == 302, f'expected redirect, got {rv.status_code}'
            fetch = models.Fetch.query.filter_by(username='remote').first()
            assert fetch is not None and fetch.folders == []
