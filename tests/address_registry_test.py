"""Focused regressions for the global User/Alias address registry.

The registry is a routing-address invariant, not a SCIM identity mapping.
These tests deliberately exercise ORM writers, raw SQL bypass attempts,
concurrent transactions, and the Alembic migration from the legacy schema.
"""

import importlib.util
import pathlib
import threading

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mailu import models


MIGRATION = (
    pathlib.Path(models.__file__).resolve().parent.parent
    / 'migrations' / 'versions' / 'd4a6f2b8c901_.py'
)


def _domain(name='example.com'):
    domain = models.Domain(name=name)
    models.db.session.add(domain)
    models.db.session.commit()
    return domain


def _user(domain, localpart='shared'):
    return models.User(
        localpart=localpart,
        domain=domain,
        password='not-a-real-password-hash',
    )


def _alias(domain, localpart='shared'):
    return models.Alias(
        localpart=localpart,
        domain=domain,
        destination=['destination@example.net'],
    )


def _enable_sqlite_foreign_keys(session):
    session.execute(sa.text('PRAGMA foreign_keys=ON'))


def _bearer(app):
    return {'Authorization': f'Bearer {app.config["API_TOKEN"]}'}


def test_registry_shares_user_alias_metadata_and_creation_order(app, tmp_path):
    assert models.MailAddress.__table__.metadata is models.User.__table__.metadata
    assert models.MailAddress.__table__.metadata is models.Alias.__table__.metadata
    assert models.MailAddress.__table__.metadata is models.db.metadata

    engine = sa.create_engine(f'sqlite:///{tmp_path / "metadata.sqlite"}')
    models.db.metadata.create_all(engine)
    models.Base.metadata.create_all(engine)
    try:
        tables = set(sa.inspect(engine).get_table_names())
        assert {'mail_address', 'user', 'alias', 'manager'} <= tables
    finally:
        models.Base.metadata.drop_all(engine)
        models.db.metadata.drop_all(engine)
        engine.dispose()


def test_user_then_alias_same_address_is_rejected_by_database(app):
    domain = _domain()
    models.db.session.add(_user(domain))
    models.db.session.commit()

    models.db.session.add(_alias(domain))
    with pytest.raises(models.AddressConflict):
        models.db.session.commit()
    models.db.session.rollback()

    assert models.User.query.count() == 1
    assert models.Alias.query.count() == 0
    assert models.MailAddress.query.count() == 1


def test_alias_then_user_same_address_is_rejected_by_database(app):
    domain = _domain()
    models.db.session.add(_alias(domain))
    models.db.session.commit()

    models.db.session.add(_user(domain))
    with pytest.raises(models.AddressConflict):
        models.db.session.commit()
    models.db.session.rollback()

    assert models.User.query.count() == 0
    assert models.Alias.query.count() == 1
    assert models.MailAddress.query.count() == 1


def test_concurrent_user_alias_claim_has_exactly_one_winner(app, tmp_path):
    database = tmp_path / 'address-race.sqlite'
    engine = sa.create_engine(
        f'sqlite:///{database}',
        connect_args={'check_same_thread': False, 'timeout': 10},
    )

    @sa.event.listens_for(engine, 'connect')
    def enable_foreign_keys(connection, _record):
        connection.execute('PRAGMA foreign_keys=ON')

    models.db.metadata.create_all(engine)
    models.Base.metadata.create_all(engine)
    with Session(engine) as seed:
        seed.add(models.Domain(name='example.com'))
        seed.commit()

    barrier = threading.Barrier(2)
    outcomes = []
    outcome_lock = threading.Lock()

    def claim(model):
        with app.app_context(), Session(engine) as session:
            domain = session.get(models.Domain, 'example.com')
            resource = (
                models.User(
                    localpart='race',
                    domain=domain,
                    password='not-a-real-password-hash',
                )
                if model is models.User
                else models.Alias(
                    localpart='race',
                    domain=domain,
                    destination=['destination@example.net'],
                )
            )
            session.add(resource)
            barrier.wait()
            try:
                session.commit()
            except models.AddressConflict:
                session.rollback()
                result = 'conflict'
            else:
                result = model.__name__
            with outcome_lock:
                outcomes.append(result)

    user_thread = threading.Thread(target=claim, args=(models.User,))
    alias_thread = threading.Thread(target=claim, args=(models.Alias,))
    user_thread.start()
    alias_thread.start()
    user_thread.join(timeout=15)
    alias_thread.join(timeout=15)

    assert not user_thread.is_alive()
    assert not alias_thread.is_alive()
    assert sorted(outcomes) in (
        ['Alias', 'conflict'],
        ['User', 'conflict'],
    )
    with Session(engine) as session:
        assert session.query(models.MailAddress).count() == 1
        assert (
            session.query(models.User).count()
            + session.query(models.Alias).count()
        ) == 1
    engine.dispose()


def test_delete_release_and_rollback_are_atomic(app):
    domain = _domain()
    user = _user(domain)
    models.db.session.add(user)
    models.db.session.commit()
    email = user.email
    assert models.db.session.get(models.MailAddress, email) is not None

    models.db.session.delete(user)
    models.db.session.flush()
    assert models.db.session.get(models.MailAddress, email) is None
    models.db.session.rollback()
    models.db.session.expire_all()

    assert models.db.session.get(models.User, email) is not None
    assert models.db.session.get(models.MailAddress, email) is not None

    user = models.db.session.get(models.User, email)
    models.db.session.delete(user)
    models.db.session.commit()
    assert models.db.session.get(models.MailAddress, email) is None

    domain = models.db.session.get(models.Domain, 'example.com')
    models.db.session.add(_alias(domain))
    models.db.session.commit()
    assert models.db.session.get(models.Alias, email) is not None


def test_persisted_address_rename_is_rejected_without_registry_drift(app):
    domain = _domain()
    user = _user(domain, localpart='before')
    models.db.session.add(user)
    models.db.session.commit()

    user.email = 'after@example.com'
    with pytest.raises(models.AddressRenameError):
        models.db.session.flush()
    models.db.session.rollback()
    models.db.session.expire_all()

    assert models.db.session.get(models.User, 'before@example.com') is not None
    assert models.db.session.get(models.User, 'after@example.com') is None
    assert models.db.session.get(models.MailAddress, 'before@example.com') is not None
    assert models.db.session.get(models.MailAddress, 'after@example.com') is None


def test_raw_child_insert_without_registry_row_fails_closed(app):
    domain = _domain()
    _enable_sqlite_foreign_keys(models.db.session)

    with pytest.raises(IntegrityError):
        models.db.session.execute(
            models.Alias.__table__.insert().values(
                email='raw@example.com',
                localpart='raw',
                domain_name=domain.name,
                destination=['destination@example.net'],
            )
        )
        models.db.session.commit()
    models.db.session.rollback()

    assert models.db.session.get(models.Alias, 'raw@example.com') is None
    assert models.db.session.get(models.MailAddress, 'raw@example.com') is None


def test_v1_user_create_maps_alias_collision_to_409(app, client):
    domain = _domain()
    models.db.session.add(_alias(domain, localpart='v1-user'))
    models.db.session.commit()

    response = client.post(
        '/api/v1/user',
        json={
            'email': 'v1-user@example.com',
            'raw_password': 'not-a-real-password',
        },
        headers=_bearer(app),
    )

    assert response.status_code == 409
    assert models.db.session.get(models.User, 'v1-user@example.com') is None


def test_v1_alias_create_maps_user_collision_to_409(app, client):
    domain = _domain()
    models.db.session.add(_user(domain, localpart='v1-alias'))
    models.db.session.commit()

    response = client.post(
        '/api/v1/alias',
        json={
            'email': 'v1-alias@example.com',
            'destination': ['v1-alias@example.com'],
        },
        headers=_bearer(app),
    )

    assert response.status_code == 409
    assert models.db.session.get(models.Alias, 'v1-alias@example.com') is None


def test_v1_user_create_maps_external_reservation_to_409(app, client):
    domain = _domain()
    group_alias = _alias(domain, localpart='managed-group')
    models.db.session.add(group_alias)
    models.db.session.commit()
    group = models.create_scim_group_mapping(group_alias)
    models.db.session.commit()
    models.replace_scim_group_graph(
        group,
        member_ids=[],
        external_destinations=['reserved@example.com'],
    )
    models.db.session.commit()

    response = client.post(
        '/api/v1/user',
        json={
            'email': 'reserved@example.com',
            'raw_password': 'not-a-real-password',
        },
        headers=_bearer(app),
    )

    assert response.status_code == 409
    assert models.db.session.get(models.User, 'reserved@example.com') is None


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        'mail_address_registry_migration',
        MIGRATION,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _legacy_engine():
    engine = sa.create_engine('sqlite://')

    @sa.event.listens_for(engine, 'connect')
    def enable_foreign_keys(connection, _record):
        connection.execute('PRAGMA foreign_keys=ON')

    metadata = sa.MetaData()
    sa.Table(
        'domain',
        metadata,
        sa.Column('name', sa.String(80), primary_key=True),
    )
    sa.Table(
        'user',
        metadata,
        sa.Column('email', sa.String(255), primary_key=True),
        sa.Column('localpart', sa.String(80), nullable=False),
        sa.Column(
            'domain_name',
            sa.String(80),
            sa.ForeignKey('domain.name', name='user_domain_name_fkey'),
            nullable=False,
        ),
    )
    sa.Table(
        'alias',
        metadata,
        sa.Column('email', sa.String(255), primary_key=True),
        sa.Column('localpart', sa.String(80), nullable=False),
        sa.Column(
            'domain_name',
            sa.String(80),
            sa.ForeignKey('domain.name', name='alias_domain_name_fkey'),
            nullable=False,
        ),
        sa.Column(
            'owner_email',
            sa.String(255),
            sa.ForeignKey('user.email', name='alias_owner_email_fkey'),
            nullable=True,
        ),
    )
    sa.Table(
        'fetch',
        metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column(
            'user_email',
            sa.String(255),
            sa.ForeignKey('user.email', name='fetch_user_email_fkey'),
            nullable=False,
        ),
    )
    sa.Table(
        'token',
        metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column(
            'user_email',
            sa.String(255),
            sa.ForeignKey('user.email', name='token_user_email_fkey'),
            nullable=False,
        ),
    )
    sa.Table(
        'manager',
        metadata,
        sa.Column(
            'domain_name',
            sa.String(80),
            sa.ForeignKey('domain.name', name='manager_domain_name_fkey'),
        ),
        sa.Column(
            'user_email',
            sa.String(255),
            sa.ForeignKey('user.email', name='manager_user_email_fkey'),
        ),
    )
    sa.Table(
        'domain_access',
        metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column(
            'domain_name',
            sa.String(80),
            sa.ForeignKey(
                'domain.name',
                name='domain_access_domain_name_fkey',
            ),
            nullable=False,
        ),
        sa.Column(
            'user_email',
            sa.String(255),
            sa.ForeignKey(
                'user.email',
                name='domain_access_user_email_fkey',
            ),
            nullable=False,
        ),
    )
    metadata.create_all(engine)
    return engine


def _run_migration(engine, operation):
    migration = _load_migration()
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        migration.op = Operations(context)
        with connection.begin():
            getattr(migration, operation)()


def _seed_legacy(engine, *, collision=False):
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO domain (name) VALUES ('example.com')"
        )
        connection.exec_driver_sql(
            "INSERT INTO user (email, localpart, domain_name) "
            "VALUES ('user@example.com', 'user', 'example.com')"
        )
        alias_email = 'user@example.com' if collision else 'alias@example.com'
        alias_localpart = 'user' if collision else 'alias'
        connection.execute(
            sa.text(
                'INSERT INTO alias '
                '(email, localpart, domain_name, owner_email) '
                'VALUES (:email, :localpart, :domain, :owner)'
            ),
            {
                'email': alias_email,
                'localpart': alias_localpart,
                'domain': 'example.com',
                'owner': 'user@example.com',
            },
        )
        connection.exec_driver_sql(
            "INSERT INTO fetch (id, user_email) "
            "VALUES (1, 'user@example.com')"
        )
        connection.exec_driver_sql(
            "INSERT INTO token (id, user_email) "
            "VALUES (1, 'user@example.com')"
        )
        connection.exec_driver_sql(
            "INSERT INTO manager (domain_name, user_email) "
            "VALUES ('example.com', 'user@example.com')"
        )
        connection.exec_driver_sql(
            "INSERT INTO domain_access (id, domain_name, user_email) "
            "VALUES (1, 'example.com', 'user@example.com')"
        )


def test_migration_refuses_cross_table_collision_before_ddl():
    engine = _legacy_engine()
    _seed_legacy(engine, collision=True)

    with pytest.raises(RuntimeError, match='user@example.com'):
        _run_migration(engine, 'upgrade')

    inspector = sa.inspect(engine)
    assert 'mail_address' not in inspector.get_table_names()
    assert 'address_type' not in {
        column['name'] for column in inspector.get_columns('user')
    }
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            'SELECT COUNT(*) FROM "user"'
        ).scalar_one() == 1
        assert connection.exec_driver_sql(
            'SELECT COUNT(*) FROM alias'
        ).scalar_one() == 1
    engine.dispose()


def test_migration_backfills_constraints_and_downgrades_without_data_loss():
    engine = _legacy_engine()
    _seed_legacy(engine)

    _run_migration(engine, 'upgrade')

    inspector = sa.inspect(engine)
    assert 'mail_address' in inspector.get_table_names()
    assert {column['name'] for column in inspector.get_columns('user')} >= {
        'email',
        'address_type',
    }
    assert {column['name'] for column in inspector.get_columns('alias')} >= {
        'email',
        'address_type',
    }
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            'SELECT email, address_type FROM mail_address ORDER BY email'
        ).all() == [
            ('alias@example.com', 'alias'),
            ('user@example.com', 'user'),
        ]
        assert connection.exec_driver_sql(
            'PRAGMA foreign_key_check'
        ).all() == []

    _run_migration(engine, 'downgrade')

    inspector = sa.inspect(engine)
    assert 'mail_address' not in inspector.get_table_names()
    assert 'address_type' not in {
        column['name'] for column in inspector.get_columns('user')
    }
    assert 'address_type' not in {
        column['name'] for column in inspector.get_columns('alias')
    }
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            'SELECT email FROM "user"'
        ).all() == [('user@example.com',)]
        assert connection.exec_driver_sql(
            'SELECT email FROM alias'
        ).all() == [('alias@example.com',)]
    engine.dispose()
