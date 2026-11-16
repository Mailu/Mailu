"""Anonymous alias generation on domains that have a catch-all alias (%@domain)."""
import pytest

from mailu import models, utils


AUTH = {'Authentication': f'owner@example.com:{"a" * 32}'}


@pytest.fixture
def owner(app, create_user_and_token, grant_domain_access):
    app.config['WTF_CSRF_ENABLED'] = False
    models.db.session.add(models.Domain(name='example.com', anonmail_enabled=True))
    models.db.session.commit()
    user, _ = create_user_and_token(email='owner@example.com')
    grant_domain_access('example.com', user=user)
    return user


def add_wildcard(localpart, destination):
    models.db.session.add(models.Alias(
        email=f'{localpart}@example.com', wildcard=True, destination=[destination]))
    models.db.session.commit()


def authenticate(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = user.email
        session['_fresh'] = True


def test_api_generates_alias_despite_catch_all(client, owner):
    add_wildcard('%', owner.email)

    rv = client.post('/api/alias/random/new?hostname=www.example.org', json={}, headers=AUTH)

    assert rv.status_code == 201, rv.get_json()
    alias_email = rv.get_json()['email']
    localpart, domain_name = alias_email.split('@')
    # The new exact alias takes precedence over the catch-all.
    assert models.Alias.resolve(localpart, domain_name).email == alias_email


def test_api_specific_wildcard_still_blocks_candidate(client, owner, monkeypatch):
    add_wildcard('%', owner.email)
    add_wildcard('shop.%', 'other@example.net')
    monkeypatch.setattr(utils, 'generate_anonymous_alias_localpart', lambda hostname=None: 'shop.banana')

    rv = client.post('/api/alias/random/new', json={}, headers=AUTH)

    assert rv.status_code == 409
    assert models.Alias.query.filter_by(email='shop.banana@example.com').first() is None


def test_ui_generates_alias_despite_catch_all(client, owner):
    add_wildcard('%', owner.email)
    authenticate(client, owner)

    rv = client.post('/admin/anonalias/create', data={
        'domain': 'example.com', 'hostname': 'www.example.org', 'note': 'ui'})

    assert rv.status_code == 302
    assert rv.location.endswith('/admin/anonalias/list')
    created = models.Alias.query.filter_by(owner_email=owner.email, wildcard=False).all()
    assert len(created) == 1
    assert created[0].email.endswith('@example.com')
