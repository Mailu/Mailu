import flask
import flask_login
import pytest

from mailu import models, utils
from mailu.ui.views import users as user_views


INITIAL_GENERATION = '0' * 32


def create_user(localpart='session-user', *, enabled=True):
    domain = models.db.session.get(models.Domain, 'example.com')
    if domain is None:
        domain = models.Domain(name='example.com')
        models.db.session.add(domain)
    user = models.User(localpart=localpart, domain=domain, enabled=enabled)
    user.set_password('password', keep_sessions=True)
    # Establish the migration generation explicitly; logical rotations are
    # exercised by individual tests.
    user.auth_generation = INITIAL_GENERATION
    models.db.session.add(user)
    models.db.session.commit()
    return user


def add_authority_probe(app):
    @app.route('/_test/session-authority')
    def session_authority_probe():
        if not flask_login.current_user.is_authenticated:
            return '', 401
        return flask_login.current_user.email, 200


def seed_browser_session(client, user_id, generation=INITIAL_GENERATION):
    with client.session_transaction() as session:
        session['_user_id'] = user_id
        if generation is not None:
            session['_auth_generation'] = generation


def test_session_loader_rejects_generation_mismatch(app, client):
    add_authority_probe(app)
    with app.app_context():
        user = create_user(localpart='stale-browser')
        user_id = user.email
        user.auth_generation = '1' * 32
        models.db.session.commit()

    seed_browser_session(client, user_id, INITIAL_GENERATION)
    response = client.get('/_test/session-authority')

    assert response.status_code == 401
    with client.session_transaction() as session:
        assert '_user_id' not in session
        assert '_auth_generation' not in session


def test_session_loader_rejects_missing_user(app, client):
    add_authority_probe(app)
    seed_browser_session(client, 'deleted-user@example.com')

    response = client.get('/_test/session-authority')

    assert response.status_code == 401
    with client.session_transaction() as session:
        assert '_user_id' not in session
        assert '_auth_generation' not in session


def test_session_loader_backfills_only_legacy_initial_generation(app, client):
    add_authority_probe(app)
    with app.app_context():
        user = create_user(localpart='legacy-browser')
        user_id = user.email
        assert user.auth_generation == INITIAL_GENERATION

    seed_browser_session(client, user_id, generation=None)
    response = client.get('/_test/session-authority')

    assert response.status_code == 200
    with client.session_transaction() as session:
        assert session['_auth_generation'] == INITIAL_GENERATION


def test_session_loader_rejects_disabled_user_even_with_matching_generation(
    app,
    client,
):
    add_authority_probe(app)
    with app.app_context():
        user = create_user(localpart='disabled-browser', enabled=False)
        user_id = user.email
        generation = user.auth_generation

    seed_browser_session(client, user_id, generation)
    response = client.get('/_test/session-authority')

    assert response.status_code == 401


def test_session_loader_rejects_malformed_generation(app, client):
    add_authority_probe(app)
    with app.app_context():
        user_id = create_user(localpart='malformed-browser').email

    seed_browser_session(client, user_id, 'not-an-auth-generation')
    response = client.get('/_test/session-authority')

    assert response.status_code == 401


def test_login_wrapper_stamps_generation_and_refuses_disabled_user(app):
    with app.test_request_context('/'):
        user = create_user(localpart='login-wrapper')
        user.auth_generation = '2' * 32
        models.db.session.commit()

        assert utils.login_user(user) is True
        assert flask.session['_user_id'] == user.email
        assert flask.session['_auth_generation'] == '2' * 32

        user.enabled = False
        assert utils.login_user(user) is False


def test_password_and_enablement_changes_rotate_model_authority(app):
    with app.app_context():
        user = create_user(localpart='model-authority')
        assert user.auth_generation == INITIAL_GENERATION

        user.set_password('replacement-password', keep_sessions=True)
        password_generation = user.auth_generation
        assert password_generation != INITIAL_GENERATION

        user.enabled = False
        disabled_generation = user.auth_generation
        assert disabled_generation != password_generation

        user.enabled = False
        assert user.auth_generation == disabled_generation

        user.enabled = True
        assert user.auth_generation != disabled_generation


def test_temp_webmail_token_is_bound_to_user_generation(app):
    with app.app_context():
        user = create_user(localpart='webmail-generation')
        user.auth_generation = '3' * 32
        models.db.session.commit()

        browser_session = utils.MailuSession(app=app)
        browser_session['_user_id'] = user.email
        browser_session['_auth_generation'] = user.auth_generation
        browser_session.save()
        token = utils.gen_temp_token(user.email, browser_session)
        browser_session.save()

        assert utils.verify_temp_token(user, token) is True

        user.auth_generation = '4' * 32
        models.db.session.commit()
        assert utils.verify_temp_token(user, token) is False

        user.enabled = False
        assert utils.verify_temp_token(user, token) is False


def test_prune_sessions_removes_backing_session_and_webmail_token(app):
    with app.app_context():
        user = create_user(localpart='prune-webmail-token')
        browser_session = utils.MailuSession(app=app)
        browser_session['_user_id'] = user.email
        browser_session['_auth_generation'] = user.auth_generation
        browser_session.save()
        token = utils.gen_temp_token(user.email, browser_session)
        browser_session.save()

        assert utils.want_bytes(token) in app.session_store.list()
        assert browser_session.sid in app.session_store.list()
        assert utils.MailuSessionExtension.prune_sessions(
            uid=user.email,
        ) == 1
        assert utils.want_bytes(token) not in app.session_store.list()
        assert browser_session.sid not in app.session_store.list()


def test_stale_sessions_do_not_transfer_across_hard_delete_recreate(
    app,
    client,
):
    add_authority_probe(app)
    with app.app_context():
        old_user = create_user(localpart='recreated-authority')
        old_user_id = old_user.email
        old_generation = old_user.auth_generation

        browser_session = utils.MailuSession(app=app)
        browser_session['_user_id'] = old_user_id
        browser_session['_auth_generation'] = old_generation
        browser_session.save()
        webmail_token = utils.gen_temp_token(old_user_id, browser_session)
        browser_session.save()

        models.db.session.delete(old_user)
        models.db.session.commit()

        domain = models.db.session.get(models.Domain, 'example.com')
        replacement = models.User(
            localpart='recreated-authority',
            domain=domain,
        )
        replacement.set_password('replacement', keep_sessions=True)
        models.db.session.add(replacement)
        models.db.session.commit()

        assert replacement.auth_generation != old_generation
        assert utils.verify_temp_token(replacement, webmail_token) is False

    seed_browser_session(client, old_user_id, old_generation)
    response = client.get('/_test/session-authority')

    assert response.status_code == 401
    with client.session_transaction() as session:
        assert '_user_id' not in session
        assert '_auth_generation' not in session


def test_finish_authority_change_regenerates_before_best_effort_prune(
    app,
    monkeypatch,
):
    events = []
    with app.test_request_context('/'):
        user = create_user(localpart='finish-authority')
        user.auth_generation = '5' * 32
        models.db.session.commit()
        assert utils.login_user(user) is True
        flask.session.save()
        assert flask.session.saved is True

        user.auth_generation = '6' * 32
        models.db.session.commit()

        def record_prune(uid=None, keep=None, app=None):
            events.append(
                ('prune', uid, flask.session.saved, flask.session.sid)
            )
            return 1

        monkeypatch.setattr(
            utils.MailuSessionExtension,
            'prune_sessions',
            record_prune,
        )

        result = utils.finish_session_authority_change(
            user,
            preserve_current=True,
        )

        assert result is True
        assert flask.session['_auth_generation'] == '6' * 32
        assert events == [('prune', user.email, False, None)]


def test_finish_authority_change_rejects_concurrently_replaced_generation(
    app,
    monkeypatch,
):
    pruned = []
    with app.test_request_context('/'):
        user = create_user(localpart='concurrent-authority')
        user.auth_generation = '5' * 32
        models.db.session.commit()
        assert utils.login_user(user) is True

        # The caller committed generation 6, but a concurrent authority
        # change won the database race before the current session was rebound.
        user.auth_generation = '7' * 32
        models.db.session.commit()

        monkeypatch.setattr(
            utils.MailuSessionExtension,
            'prune_sessions',
            lambda uid=None, **_kwargs: pruned.append(uid) or 1,
        )

        result = utils.finish_session_authority_change(
            user,
            preserve_current=True,
            expected_generation='6' * 32,
            uid=user.email,
        )

        assert result is True
        assert '_user_id' not in flask.session
        assert '_auth_generation' not in flask.session
        assert pruned == [user.email]


def test_post_commit_cleanup_failure_does_not_escape(app, monkeypatch):
    with app.app_context():
        user = create_user(localpart='cleanup-failure')

        def fail_prune(**_kwargs):
            raise RuntimeError('session store unavailable')

        monkeypatch.setattr(
            utils.MailuSessionExtension,
            'prune_sessions',
            fail_prune,
        )

        assert utils.finish_session_authority_change(user) is False


class _Field:
    def __init__(self, data):
        self.data = data


class _PasswordForm:
    pw = _Field('replacement-password')
    pw2 = _Field('replacement-password')
    current_pw = _Field('password')
    pwned = _Field(-1)

    @staticmethod
    def validate_on_submit():
        return True


def test_self_password_flow_commits_before_rebinding_session(
    app,
    monkeypatch,
):
    events = []
    rebound = []
    with app.test_request_context('/user/password', method='POST'):
        user = create_user(localpart='password-order')
        assert utils.login_user(user)

        monkeypatch.setattr(
            models.User,
            'login',
            classmethod(lambda _cls, _email, _password: user),
        )

        def set_password(_password, **_kwargs):
            events.append('set-password')
            user.auth_generation = '7' * 32

        monkeypatch.setattr(user, 'set_password', set_password)
        monkeypatch.setattr(
            models.db.session,
            'commit',
            lambda: events.append('commit'),
        )

        def finish(changed_user, **kwargs):
            events.append('finish')
            rebound.append((changed_user, kwargs))

        monkeypatch.setattr(
            utils,
            'finish_session_authority_change',
            finish,
        )
        monkeypatch.setattr(flask, 'render_template', lambda *_a, **_k: '')

        user_views._process_password_change(_PasswordForm(), None)

    assert events == ['set-password', 'commit', 'finish']
    assert rebound == [
        (
            user,
            {
                'preserve_current': True,
                'expected_generation': '7' * 32,
                'uid': user.email,
            },
        ),
    ]


def test_failed_password_commit_does_not_regenerate_or_prune(
    app,
    monkeypatch,
):
    events = []
    with app.test_request_context('/user/password', method='POST'):
        user = create_user(localpart='password-rollback')
        assert utils.login_user(user)
        flask.session.save()
        original_key = flask.session._key

        monkeypatch.setattr(
            models.User,
            'login',
            classmethod(lambda _cls, _email, _password: user),
        )
        monkeypatch.setattr(
            user,
            'set_password',
            lambda *_args, **_kwargs: events.append('set-password'),
        )

        def fail_commit():
            events.append('commit')
            raise RuntimeError('database unavailable')

        monkeypatch.setattr(models.db.session, 'commit', fail_commit)
        monkeypatch.setattr(
            utils,
            'finish_session_authority_change',
            lambda *_args, **_kwargs: events.append('finish'),
        )

        with pytest.raises(RuntimeError, match='database unavailable'):
            user_views._process_password_change(_PasswordForm(), None)

        assert events == ['set-password', 'commit']
        assert flask.session.saved is True
        assert flask.session._key == original_key


def test_user_app_tokens_remain_separate_from_browser_generation(app):
    with app.app_context():
        user = create_user(localpart='app-token-separation')
        token = models.Token(user_email=user.email)
        token.set_password('a' * 32)
        models.db.session.add(token)
        models.db.session.commit()

        original_generation = user.auth_generation
        assert utils.check_credentials_for_api(user, 'a' * 32, '127.0.0.1')
        assert user.auth_generation == original_generation
