"""Regression tests for #4061.

The `/api/v1/alias/me*` endpoints read `flask.g.user`, which only
`common.user_token_authorization` sets. They were decorated with
`common.api_token_authorization` instead, so the documented caller (a global
`API_TOKEN` bearer) hit `flask_login.current_user` — an `AnonymousUserMixin`
with no `.email` — and the request died with a 500.
"""

import pytest

from mailu import models


TOKEN = 'a' * 32


@pytest.fixture
def anon_alias(app, create_user_and_token):
    """A user owning one anonymous alias, plus a second user owning another."""
    def _setup():
        models.db.session.add(models.Domain(name='example.com', anonmail_enabled=True))
        models.db.session.commit()

        user, _ = create_user_and_token(email='owner@example.com')
        other, _ = create_user_and_token(email='other@example.com')

        mine = models.Alias(
            localpart='mine', domain_name='example.com',
            destination=[user.email], owner_email=user.email, wildcard=False,
        )
        theirs = models.Alias(
            localpart='theirs', domain_name='example.com',
            destination=[other.email], owner_email=other.email, wildcard=False,
        )
        models.db.session.add_all([mine, theirs])
        models.db.session.commit()
        return user, other, mine.email, theirs.email
    return _setup


def user_auth(email):
    return {'Authentication': f'{email}:{TOKEN}'}


class TestAliasMeAuthentication:

    def test_get_me_with_user_token(self, app, client, anon_alias):
        """The per-user token is the auth these endpoints were written for."""
        with app.app_context():
            user, _other, mine, _theirs = anon_alias()

            rv = client.get('/api/v1/alias/me', headers=user_auth(user.email))

            assert rv.status_code == 200
            assert [a['email'] for a in rv.get_json()] == [mine]

    def test_get_me_does_not_leak_other_users_aliases(self, app, client, anon_alias):
        with app.app_context():
            user, _other, _mine, theirs = anon_alias()

            rv = client.get('/api/v1/alias/me', headers=user_auth(user.email))

            assert rv.status_code == 200
            assert theirs not in [a['email'] for a in rv.get_json()]

    def test_patch_me_with_user_token(self, app, client, anon_alias):
        with app.app_context():
            user, _other, mine, _theirs = anon_alias()

            rv = client.patch(f'/api/v1/alias/me/{mine}', json={'comment': 'note'},
                              headers=user_auth(user.email))

            assert rv.status_code == 200
            assert models.Alias.query.filter_by(email=mine).first().comment == 'note'

    def test_delete_me_with_user_token(self, app, client, anon_alias):
        with app.app_context():
            user, _other, mine, _theirs = anon_alias()

            rv = client.delete(f'/api/v1/alias/me/{mine}', headers=user_auth(user.email))

            assert rv.status_code == 200
            assert models.Alias.query.filter_by(email=mine).first() is None

    def test_patch_me_cannot_touch_another_users_alias(self, app, client, anon_alias):
        with app.app_context():
            user, _other, _mine, theirs = anon_alias()

            rv = client.patch(f'/api/v1/alias/me/{theirs}', json={'comment': 'stolen'},
                              headers=user_auth(user.email))

            assert rv.status_code == 404
            assert models.Alias.query.filter_by(email=theirs).first().comment != 'stolen'

    def test_delete_me_cannot_touch_another_users_alias(self, app, client, anon_alias):
        with app.app_context():
            user, _other, _mine, theirs = anon_alias()

            rv = client.delete(f'/api/v1/alias/me/{theirs}', headers=user_auth(user.email))

            assert rv.status_code == 404
            assert models.Alias.query.filter_by(email=theirs).first() is not None


class TestAliasMeNoLongerCrashes:
    """The reported symptom: a caller without a usable identity got a 500."""

    @pytest.mark.parametrize('request_call', [
        lambda c, h: c.get('/api/v1/alias/me', headers=h),
        lambda c, h: c.delete('/api/v1/alias/me/mine@example.com', headers=h),
        lambda c, h: c.patch('/api/v1/alias/me/mine@example.com', json={}, headers=h),
    ], ids=['get', 'delete', 'patch'])
    def test_admin_bearer_token_is_rejected_not_a_500(self, app, client, anon_alias, request_call):
        with app.app_context():
            anon_alias()
            headers = {'Authorization': f'Bearer {app.config["API_TOKEN"]}'}

            rv = request_call(client, headers)

            assert rv.status_code == 401

    @pytest.mark.parametrize('request_call', [
        lambda c, h: c.get('/api/v1/alias/me', headers=h),
        lambda c, h: c.delete('/api/v1/alias/me/mine@example.com', headers=h),
        lambda c, h: c.patch('/api/v1/alias/me/mine@example.com', json={}, headers=h),
    ], ids=['get', 'delete', 'patch'])
    def test_unauthenticated_is_rejected_not_a_500(self, app, client, anon_alias, request_call):
        with app.app_context():
            anon_alias()

            rv = request_call(client, {})

            assert rv.status_code == 401

    def test_bad_user_token_is_rejected(self, app, client, anon_alias):
        with app.app_context():
            user, _other, _mine, _theirs = anon_alias()

            rv = client.get('/api/v1/alias/me',
                            headers={'Authentication': f'{user.email}:{"b" * 32}'})

            assert rv.status_code == 403
