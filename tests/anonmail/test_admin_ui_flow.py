""" Regression tests for two admin-UI flow bugs:

    - The forced-password-change view stored the post-change destination under
      session['redirect_to'] but read session['redir_to'] -> the key never
      matched, so it always redirected to WEB_ADMIN instead of the chosen target.
    - The Create-User view called form.process() on the failed-submit path, which
      re-initialised the form and discarded the admin's input and the validation
      errors, showing an empty form with no feedback.
"""

from mailu import models


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.get_id()
        sess['_fresh'] = True


def test_forced_pw_change_redirects_to_stored_destination(app, client):
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        models.db.session.add(models.Domain(name='example.com'))
        user = models.User(localpart='u', domain_name='example.com')
        user.set_password('oldpassword')
        user.change_pw_next_login = True
        models.db.session.add(user)
        models.db.session.commit()

        _login(client, user)
        with client.session_transaction() as sess:
            sess['redirect_to'] = 'http://localhost/webmail/'

        rv = client.post('/sso/pw_change', data={
            'oldpw': 'oldpassword', 'pw': 'N3wStr0ngPass!xyz', 'pw2': 'N3wStr0ngPass!xyz',
            'pwned': '0', 'submit': 'Change password'})
        assert rv.status_code == 302
        assert rv.headers['Location'] == 'http://localhost/webmail/'


def test_user_create_invalid_submit_preserves_input(app, client):
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        models.db.session.add(models.Domain(name='example.com'))
        admin = models.User(localpart='admin', domain_name='example.com')
        admin.set_password('password')
        admin.global_admin = True
        models.db.session.add(admin)
        models.db.session.commit()

        _login(client, admin)
        prefix = app.config['WEB_ADMIN']
        # pw != pw2 -> invalid submit that falls through to the re-render
        rv = client.post(f'{prefix}/user/create/example.com', data={
            'localpart': 'keepme', 'pw': 'Secret123!abc', 'pw2': 'DIFFERENT!abc',
            'quota_bytes': '1000000000', 'comment': '', 'submit': 'Save'})
        assert rv.status_code == 200
        assert b'keepme' in rv.data, 'entered localpart was discarded on failed submit'
