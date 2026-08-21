from mailu import models, utils
from mailu.schemas import MailuSchema


INITIAL_GENERATION = utils.INITIAL_AUTH_GENERATION


def create_user(localpart='authority-model'):
    domain = models.db.session.get(models.Domain, 'example.com')
    if domain is None:
        domain = models.Domain(name='example.com')
        models.db.session.add(domain)
    user = models.User(localpart=localpart, domain=domain)
    user.set_password('initial-password', keep_sessions=True)
    models.db.session.add(user)
    models.db.session.commit()
    return user


def update_import(source):
    context = {
        'import': True,
        'update': True,
        'clear': False,
        'callback': lambda *args, **kwargs: None,
    }
    schema = MailuSchema(only=MailuSchema.Meta.order, context=context)
    with models.db.session.no_autoflush:
        schema.loads(source)
    models.db.session.commit()


def test_new_user_starts_at_random_generation(app):
    user = create_user()

    assert user.auth_generation != INITIAL_GENERATION
    assert len(user.auth_generation) == 32
    assert set(user.auth_generation) <= set('0123456789abcdef')
    assert user.is_active is True


def test_logical_password_replacement_rotates_generation_in_sql(app):
    user = create_user(localpart='password-rotation')
    before = user.auth_generation

    user.set_password('replacement-password', keep_sessions=True)
    rotated = user.auth_generation
    models.db.session.commit()

    assert rotated != before
    assert len(rotated) == 32
    assert set(rotated) <= set('0123456789abcdef')
    assert models.db.session.get(models.User, user.email).auth_generation == rotated


def test_raw_hash_replacement_rotates_but_same_hash_does_not(app):
    user = create_user(localpart='raw-rotation')
    existing_hash = user.password
    before = user.auth_generation

    user.set_password(existing_hash, raw=True, keep_sessions=True)
    assert user.auth_generation == before

    user.set_password('{CRYPT}$6$replacement', raw=True, keep_sessions=True)
    assert user.auth_generation != before


def test_direct_orm_password_assignment_rotates_for_config_import(app):
    user = create_user(localpart='import-rotation')
    before = user.auth_generation

    user.password = user.password + '-imported'

    assert user.auth_generation != before


def test_update_import_same_plaintext_password_keeps_generation(app):
    user = create_user(localpart='same-import-password')
    before_hash = user.password
    before_generation = user.auth_generation

    update_import(
        'user:\n'
        f'  - email: {user.email}\n'
        '    password: initial-password\n'
        '    hash_password: true\n'
    )

    assert user.password == before_hash
    assert user.auth_generation == before_generation


def test_update_import_same_password_with_disable_still_rotates(app):
    user = create_user(localpart='same-import-password-disable')
    before_hash = user.password
    before_generation = user.auth_generation

    update_import(
        'user:\n'
        f'  - email: {user.email}\n'
        '    password: initial-password\n'
        '    hash_password: true\n'
        '    enabled: false\n'
    )

    assert user.password == before_hash
    assert user.enabled is False
    assert user.auth_generation != before_generation


def test_update_import_same_plaintext_token_keeps_hash(app):
    user = create_user(localpart='same-import-token')
    raw_token = 'a' * 32
    token = models.Token(user_email=user.email)
    token.set_password(raw_token)
    models.db.session.add(token)
    models.db.session.commit()
    before_hash = token.password

    update_import(
        'user:\n'
        f'  - email: {user.email}\n'
        '    tokens:\n'
        f'      - id: {token.id}\n'
        f'        password: {raw_token}\n'
        '        hash_password: true\n'
    )

    assert models.db.session.get(
        models.Token,
        token.id,
    ).password == before_hash


def test_enablement_change_rotates_but_same_value_does_not(app):
    user = create_user(localpart='enabled-rotation')
    before = user.auth_generation

    user.enabled = True
    assert user.auth_generation == before

    user.enabled = False
    disabled_generation = user.auth_generation
    assert disabled_generation != before
    assert user.is_active is False

    user.enabled = False
    assert user.auth_generation == disabled_generation

    user.enabled = True
    assert user.auth_generation != disabled_generation
    assert user.is_active is True


def test_rollback_restores_generation_and_authority(app):
    user = create_user(localpart='rollback-generation')
    before = user.auth_generation

    user.enabled = False
    assert user.auth_generation != before
    models.db.session.rollback()

    restored = models.db.session.get(models.User, user.email)
    assert restored.enabled is True
    assert restored.auth_generation == before


def test_transparent_password_rehash_does_not_rotate_generation(app, monkeypatch):
    user = create_user(localpart='rehash-generation')
    before = user.auth_generation
    replacement_hash = user.password + '-rehash'

    class _Context:
        @staticmethod
        def verify_and_update(_password, _reference):
            return True, replacement_hash

    monkeypatch.setattr(
        models.User,
        'get_password_context',
        classmethod(lambda _cls: _Context()),
    )

    assert user.check_password('initial-password') is True
    assert user.password == replacement_hash
    assert user.auth_generation == before
