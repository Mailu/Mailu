"""Real populated Alembic upgrade coverage for native SQL backends."""

from datetime import date, datetime
import os
import pathlib
import re

from alembic import command
from flask import current_app
import pytest
import sqlalchemy as sa

from mailu import configuration, create_app_from_config, models


BASE_REVISION = '9a5866105f5a'
ADDRESS_REVISION = 'd4a6f2b8c901'
HEAD_REVISION = 'e7c9a4f2b631'
MIGRATIONS = pathlib.Path(models.__file__).resolve().parent.parent / 'migrations'
INITIAL_AUTH_GENERATION = '0' * 32
MYSQL_FAMILY = {'mysql', 'mariadb'}
SAFE_DATABASE = 'mailu_scim_test'
SAFE_HOSTS = {'127.0.0.1', 'localhost'}
SAFE_IDENTIFIER = re.compile(r'^[A-Za-z0-9_]+$')
EXPECTED_BACKFILL_BATCH_SIZE = 128
EXPECTED_COLLISION_PROBE_LIMIT = 21


def _assert_safe_target(engine):
    url = engine.url
    if (
        engine.dialect.name not in MYSQL_FAMILY | {'postgresql'}
        or url.host not in SAFE_HOSTS
        or url.database != SAFE_DATABASE
    ):
        raise AssertionError(
            'refusing destructive native migration test against '
            f'{url.render_as_string(hide_password=True)}'
        )


def _mysql_database_default(engine):
    if engine.dialect.name not in MYSQL_FAMILY:
        return None
    with engine.connect() as connection:
        database_name, character_set, collation = connection.execute(sa.text(
            """
            SELECT SCHEMA_NAME, DEFAULT_CHARACTER_SET_NAME,
                   DEFAULT_COLLATION_NAME
              FROM information_schema.SCHEMATA
             WHERE SCHEMA_NAME = DATABASE()
            """
        )).one()
    return database_name, character_set, collation


def _restore_mysql_database_default(engine, storage):
    if storage is None:
        return
    database_name, character_set, collation = storage
    if not all(
        SAFE_IDENTIFIER.fullmatch(value)
        for value in storage
    ):
        raise AssertionError('database returned an unsafe identifier')
    with engine.connect() as connection:
        quote = connection.dialect.identifier_preparer.quote
        connection.exec_driver_sql(
            f'ALTER DATABASE {quote(database_name)} '
            f'CHARACTER SET {character_set} COLLATE {collation}'
        )
        connection.commit()


def _set_mysql_database_default(engine, character_set, collation):
    if engine.dialect.name not in MYSQL_FAMILY:
        raise AssertionError('requires MariaDB/MySQL')
    with engine.connect() as connection:
        database_name = connection.scalar(sa.text('SELECT DATABASE()'))
        available = connection.scalar(sa.text(
            """
            SELECT COUNT(*)
              FROM information_schema.COLLATIONS
             WHERE CHARACTER_SET_NAME = :character_set
               AND COLLATION_NAME = :collation
            """
        ), {
            'character_set': character_set,
            'collation': collation,
        })
    if available != 1:
        raise AssertionError(
            f'collation {collation!r} is not available for {character_set!r}'
        )
    _restore_mysql_database_default(
        engine,
        (database_name, character_set, collation),
    )


def _reset_database(engine):
    models.db.session.remove()
    if engine.dialect.name == 'postgresql':
        with engine.begin() as connection:
            connection.exec_driver_sql('DROP SCHEMA IF EXISTS public CASCADE')
            connection.exec_driver_sql('CREATE SCHEMA public')
        return

    if engine.dialect.name in MYSQL_FAMILY:
        with engine.connect() as connection:
            try:
                connection.exec_driver_sql('SET FOREIGN_KEY_CHECKS=0')
                inspector = sa.inspect(connection)
                quote = connection.dialect.identifier_preparer.quote
                for table_name in inspector.get_table_names():
                    connection.exec_driver_sql(
                        f'DROP TABLE IF EXISTS {quote(table_name)}'
                    )
            finally:
                connection.exec_driver_sql('SET FOREIGN_KEY_CHECKS=1')
                connection.commit()
        return

    raise AssertionError(f'unsupported native test dialect {engine.dialect.name}')


@pytest.fixture
def native_migration_app(env_setup):
    if os.environ.get('MAILU_NATIVE_MIGRATION_TEST') != '1':
        pytest.skip('native migration test is destructive and explicitly gated')

    app = create_app_from_config(configuration.ConfigManager())
    app.config['TESTING'] = True
    with app.app_context():
        engine = models.db.engine
        _assert_safe_target(engine)
        original_mysql_default = _mysql_database_default(engine)
        _reset_database(engine)
        try:
            yield app
        finally:
            try:
                _reset_database(engine)
            finally:
                _restore_mysql_database_default(
                    engine,
                    original_mysql_default,
                )
                models.db.session.remove()
                engine.dispose()


def _upgrade(revision):
    config = current_app.extensions['migrate'].migrate.get_config(
        str(MIGRATIONS)
    )
    command.upgrade(config, revision)


def _tables(connection, *names):
    metadata = sa.MetaData()
    return {
        name: sa.Table(name, metadata, autoload_with=connection)
        for name in names
    }


def _snapshot_tables(connection, tables):
    snapshots = {}
    for name, table in tables.items():
        column_names = tuple(column.name for column in table.columns)
        order_by = list(table.primary_key.columns) or list(table.columns)
        rows = connection.execute(
            sa.select(*(table.c[column] for column in column_names)).order_by(
                *order_by
            )
        ).all()
        snapshots[name] = (column_names, rows)
    return snapshots


def _assert_table_snapshots(engine, snapshots):
    with engine.connect() as connection:
        tables = _tables(connection, *snapshots)
        for name, (column_names, expected_rows) in snapshots.items():
            table = tables[name]
            order_by = list(table.primary_key.columns) or [
                table.c[column] for column in column_names
            ]
            actual_rows = connection.execute(
                sa.select(*(
                    table.c[column] for column in column_names
                )).order_by(*order_by)
            ).all()
            assert actual_rows == expected_rows


def _legacy_user(email, domain_name, *, global_admin=False):
    localpart = email.rsplit('@', 1)[0]
    return {
        'created_at': date(2024, 1, 2),
        'updated_at': date(2024, 1, 3),
        'comment': f'legacy {localpart}',
        'localpart': localpart,
        'password': 'not-a-real-password-hash',
        'quota_bytes': 1_000_000,
        'global_admin': global_admin,
        'enable_imap': True,
        'enable_pop': False,
        'forward_enabled': True,
        'forward_destination': 'archive@outside.example',
        'reply_enabled': False,
        'reply_subject': None,
        'reply_body': None,
        'displayed_name': f'Legacy {localpart}',
        'spam_enabled': True,
        'domain_name': domain_name,
        'email': email,
        'spam_threshold': 75,
        'forward_keep': True,
        'reply_enddate': date(2999, 12, 31),
        'enabled': True,
        'quota_bytes_used': 123,
        'reply_startdate': date(1900, 1, 1),
        'spam_mark_as_read': False,
        'allow_spoofing': True,
        'change_pw_next_login': False,
    }


def _seed_populated_legacy_database(engine):
    with engine.begin() as connection:
        table = _tables(
            connection,
            'domain',
            'user',
            'alias',
            'fetch',
            'token',
            'manager',
            'domain_access',
        )
        connection.execute(table['domain'].insert(), [
            {
                'created_at': date(2024, 1, 1),
                'updated_at': None,
                'comment': 'ASCII domain',
                'name': 'example.com',
                'max_users': -1,
                'max_aliases': -1,
                'max_quota_bytes': 0,
                'signup_enabled': False,
                'anonmail_enabled': True,
            },
            {
                'created_at': date(2024, 1, 1),
                'updated_at': None,
                'comment': 'IDNA domain',
                'name': 'xn--bcher-kva.example',
                'max_users': -1,
                'max_aliases': -1,
                'max_quota_bytes': 0,
                'signup_enabled': False,
                'anonmail_enabled': False,
            },
        ])
        connection.execute(table['user'].insert(), [
            _legacy_user(
                'admin@example.com',
                'example.com',
                global_admin=True,
            ),
            _legacy_user(
                'member@xn--bcher-kva.example',
                'xn--bcher-kva.example',
            ),
        ])
        connection.execute(table['alias'].insert().values(
            created_at=date(2024, 1, 4),
            updated_at=date(2024, 1, 5),
            comment='Legacy list',
            localpart='list',
            destination='admin@example.com,pager@outside.example',
            domain_name='example.com',
            email='list@example.com',
            wildcard=False,
            hostname='list.example.com',
            owner_email='admin@example.com',
            disabled=False,
        ))
        connection.execute(table['fetch'].insert().values(
            id=41,
            created_at=date(2024, 1, 6),
            updated_at=None,
            comment='Legacy fetch',
            user_email='admin@example.com',
            protocol='imap',
            host='imap.outside.example',
            port=993,
            tls=True,
            username='remote-user',
            password='remote-password',
            error=None,
            last_check=None,
            keep=True,
            scan=True,
            folders='INBOX',
            invisible=False,
        ))
        connection.execute(table['token'].insert().values(
            id=42,
            created_at=date(2024, 1, 7),
            updated_at=None,
            comment='Legacy token',
            user_email='admin@example.com',
            password='a' * 32,
            ip='127.0.0.1',
        ))
        connection.execute(table['manager'].insert().values(
            domain_name='example.com',
            user_email='admin@example.com',
        ))
        connection.execute(table['domain_access'].insert().values(
            id=43,
            domain_name='example.com',
            user_email='admin@example.com',
            created_at=date(2024, 1, 8),
            updated_at=None,
            comment='Legacy grant',
        ))
        return _snapshot_tables(connection, table)


def _seed_invalid_identity(engine):
    with engine.begin() as connection:
        table = _tables(connection, 'domain', 'user')
        connection.execute(table['domain'].insert().values(
            created_at=date(2024, 1, 1),
            updated_at=None,
            comment='Invalid IDNA domain',
            name='xn--',
            max_users=-1,
            max_aliases=-1,
            max_quota_bytes=0,
            signup_enabled=False,
            anonmail_enabled=False,
        ))
        connection.execute(
            table['user'].insert().values(
                **_legacy_user('invalid@xn--', 'xn--')
            )
        )


def _seed_duplicate_published_identity(engine):
    domains = ('xn--bcher-kva.example', 'bücher.example')
    with engine.begin() as connection:
        table = _tables(connection, 'domain', 'user')
        connection.execute(table['domain'].insert(), [
            {
                'created_at': date(2024, 1, 1),
                'updated_at': None,
                'comment': 'Duplicate published SCIM ID',
                'name': domain_name,
                'max_users': -1,
                'max_aliases': -1,
                'max_quota_bytes': 0,
                'signup_enabled': False,
                'anonmail_enabled': False,
            }
            for domain_name in domains
        ])
        connection.execute(table['user'].insert(), [
            _legacy_user(f'member@{domain_name}', domain_name)
            for domain_name in domains
        ])


def _seed_non_latin_idna_identity(engine):
    domain_name = 'xn--e1afmkfd.xn--p1ai'
    email = f'member@{domain_name}'
    with engine.begin() as connection:
        table = _tables(connection, 'domain', 'user')
        connection.execute(table['domain'].insert().values(
            created_at=date(2024, 1, 1),
            updated_at=None,
            comment='Cyrillic IDNA domain',
            name=domain_name,
            max_users=-1,
            max_aliases=-1,
            max_quota_bytes=0,
            signup_enabled=False,
            anonmail_enabled=False,
        ))
        connection.execute(
            table['user'].insert().values(
                **_legacy_user(email, domain_name)
            )
        )
    return email, 'member@\u043f\u0440\u0438\u043c\u0435\u0440.\u0440\u0444'


def _seed_backfill_population(engine, count, *, alias_count=0):
    domain_name = 'batch.example'
    with engine.begin() as connection:
        table = _tables(connection, 'domain', 'user', 'alias')
        connection.execute(table['domain'].insert().values(
            created_at=date(2024, 1, 1),
            updated_at=None,
            comment='Backfill batch domain',
            name=domain_name,
            max_users=-1,
            max_aliases=-1,
            max_quota_bytes=0,
            signup_enabled=False,
            anonmail_enabled=False,
        ))
        connection.execute(table['user'].insert(), [
            _legacy_user(f'batch{index:04d}@{domain_name}', domain_name)
            for index in range(count)
        ])
        if alias_count:
            connection.execute(table['alias'].insert(), [
                {
                    'created_at': date(2024, 1, 1),
                    'updated_at': None,
                    'comment': 'Backfill batch Alias',
                    'localpart': f'route{index:04d}',
                    'destination': 'outside@example.net',
                    'domain_name': domain_name,
                    'email': f'route{index:04d}@{domain_name}',
                    'wildcard': False,
                    'hostname': None,
                    'owner_email': None,
                    'disabled': False,
                }
                for index in range(alias_count)
            ])


def _mysql_column_storage(connection, table_name, column_name):
    return connection.execute(sa.text(
        """
        SELECT CHARACTER_SET_NAME, COLLATION_NAME
          FROM information_schema.COLUMNS
         WHERE TABLE_SCHEMA = DATABASE()
           AND TABLE_NAME = :table_name
           AND COLUMN_NAME = :column_name
        """
    ), {
        'table_name': table_name,
        'column_name': column_name,
    }).one()


def _alternate_mysql_collation(connection, character_set, current):
    candidates = connection.execute(sa.text(
        """
        SELECT COLLATION_NAME
          FROM information_schema.COLLATIONS
         WHERE CHARACTER_SET_NAME = :character_set
           AND COLLATION_NAME <> :current
           AND COLLATION_NAME NOT LIKE '%\\_bin'
         ORDER BY COLLATION_NAME
        """
    ), {
        'character_set': character_set,
        'current': current,
    }).scalars().all()
    if not candidates:
        raise AssertionError('no alternate database collation is available')
    preferred = [
        f'{character_set}_unicode_ci',
        f'{character_set}_general_ci',
    ]
    return next(
        (name for name in preferred if name in candidates),
        candidates[0],
    )


def _change_mysql_database_default(engine):
    if engine.dialect.name not in MYSQL_FAMILY:
        return None

    with engine.connect() as connection:
        database_name = connection.scalar(sa.text('SELECT DATABASE()'))
        character_set, legacy_collation = _mysql_column_storage(
            connection,
            'user',
            'email',
        )
        target = _alternate_mysql_collation(
            connection,
            character_set,
            legacy_collation,
        )
        if not all(
            SAFE_IDENTIFIER.fullmatch(value)
            for value in (database_name, character_set, target)
        ):
            raise AssertionError('database returned an unsafe identifier')
        quote = connection.dialect.identifier_preparer.quote
        connection.exec_driver_sql(
            f'ALTER DATABASE {quote(database_name)} '
            f'CHARACTER SET {character_set} COLLATE {target}'
        )
        connection.commit()
    return legacy_collation, target


def _force_alias_email_collation_mismatch(engine):
    with engine.connect() as connection:
        character_set, current = _mysql_column_storage(
            connection,
            'alias',
            'email',
        )
        target = _alternate_mysql_collation(
            connection,
            character_set,
            current,
        )
        if not all(
            SAFE_IDENTIFIER.fullmatch(value)
            for value in (character_set, target)
        ):
            raise AssertionError('database returned an unsafe identifier')
        quote = connection.dialect.identifier_preparer.quote
        connection.exec_driver_sql(
            f'ALTER TABLE {quote("alias")} MODIFY {quote("email")} '
            f'VARCHAR(255) CHARACTER SET {character_set} COLLATE {target} '
            'NOT NULL'
        )
        connection.commit()
    return current, target


def _assert_foreign_key(
    inspector,
    table_name,
    constraint_name,
    constrained_columns,
    referred_table,
    referred_columns,
):
    constraint = next(
        foreign_key
        for foreign_key in inspector.get_foreign_keys(table_name)
        if foreign_key['name'] == constraint_name
    )
    assert constraint['constrained_columns'] == constrained_columns
    assert constraint['referred_table'] == referred_table
    assert constraint['referred_columns'] == referred_columns


def _assert_member_index(inspector):
    index = next(
        index
        for index in inspector.get_indexes('scim_group_member')
        if index['name'] == 'scim_group_member_member_id_idx'
    )
    assert index['column_names'] == ['member_id']
    assert index['unique'] is False

    model_index = next(
        index
        for index in models.ScimGroupMember.__table__.indexes
        if index.name == 'scim_group_member_member_id_idx'
    )
    assert [column.name for column in model_index.columns] == ['member_id']
    assert model_index.unique is False


def _assert_native_constraints(inspector):
    expected_foreign_keys = (
        (
            'user',
            'user_mail_address_fkey',
            ['email', 'address_type'],
            'mail_address',
            ['email', 'address_type'],
        ),
        (
            'alias',
            'alias_mail_address_fkey',
            ['email', 'address_type'],
            'mail_address',
            ['email', 'address_type'],
        ),
        (
            'scim_resource',
            'scim_resource_user_email_fkey',
            ['user_email'],
            'user',
            ['email'],
        ),
        (
            'scim_resource',
            'scim_resource_alias_email_fkey',
            ['alias_email'],
            'alias',
            ['email'],
        ),
        (
            'scim_group_member',
            'scim_group_member_group_id_fkey',
            ['group_id'],
            'scim_resource',
            ['id'],
        ),
        (
            'scim_group_member',
            'scim_group_member_member_id_fkey',
            ['member_id'],
            'scim_resource',
            ['id'],
        ),
        (
            'scim_group_destination',
            'scim_group_destination_group_id_fkey',
            ['group_id'],
            'scim_resource',
            ['id'],
        ),
    )
    for expected in expected_foreign_keys:
        _assert_foreign_key(inspector, *expected)

    expected_checks = {
        'mail_address': {'mail_address_type_check'},
        'user': {'user_address_type_check'},
        'alias': {'alias_address_type_check'},
        'scim_state': {'scim_state_singleton_check'},
        'scim_resource': {
            'scim_resource_type_check',
            'scim_resource_lifecycle_check',
        },
    }
    for table_name, names in expected_checks.items():
        assert names <= {
            constraint['name']
            for constraint in inspector.get_check_constraints(table_name)
        }
    _assert_member_index(inspector)


def _assert_populated_upgrade(engine, changed_default, snapshots):
    inspector = sa.inspect(engine)
    assert {
        'mail_address',
        'scim_state',
        'scim_resource',
        'scim_group_member',
        'scim_group_destination',
    } <= set(inspector.get_table_names())
    _assert_native_constraints(inspector)
    _assert_table_snapshots(engine, snapshots)
    auth_generation = next(
        column
        for column in inspector.get_columns('user')
        if column['name'] == 'auth_generation'
    )
    assert auth_generation['nullable'] is False
    assert auth_generation['default'] is None

    with engine.begin() as connection:
        table = _tables(
            connection,
            'alembic_version',
            'user',
            'alias',
            'fetch',
            'token',
            'manager',
            'domain_access',
            'mail_address',
            'scim_resource',
            'scim_state',
            'scim_group_member',
            'scim_group_destination',
        )
        assert connection.scalar(
            sa.select(table['alembic_version'].c.version_num)
        ) == HEAD_REVISION
        assert set(connection.execute(sa.select(
            table['user'].c.email,
            table['user'].c.auth_generation,
        ))) == {
            ('admin@example.com', INITIAL_AUTH_GENERATION),
            ('member@xn--bcher-kva.example', INITIAL_AUTH_GENERATION),
        }
        assert connection.execute(sa.select(
            table['alias'].c.email,
            table['alias'].c.destination,
            table['alias'].c.owner_email,
        )).all() == [(
            'list@example.com',
            'admin@example.com,pager@outside.example',
            'admin@example.com',
        )]
        assert connection.execute(sa.select(
            table['fetch'].c.id,
            table['fetch'].c.user_email,
            table['fetch'].c.protocol,
            table['fetch'].c.folders,
        )).all() == [(41, 'admin@example.com', 'imap', 'INBOX')]
        assert connection.execute(sa.select(
            table['token'].c.id,
            table['token'].c.user_email,
            table['token'].c.comment,
        )).all() == [(42, 'admin@example.com', 'Legacy token')]
        assert connection.execute(sa.select(table['manager'])).all() == [
            ('example.com', 'admin@example.com'),
        ]
        assert connection.execute(sa.select(
            table['domain_access'].c.id,
            table['domain_access'].c.domain_name,
            table['domain_access'].c.user_email,
        )).all() == [(43, 'example.com', 'admin@example.com')]
        assert set(connection.execute(sa.select(
            table['mail_address'].c.email,
            table['mail_address'].c.address_type,
        ))) == {
            ('admin@example.com', 'user'),
            ('member@xn--bcher-kva.example', 'user'),
            ('list@example.com', 'alias'),
        }
        assert connection.execute(sa.select(
            table['scim_resource'].c.id,
            table['scim_resource'].c.resource_type,
            table['scim_resource'].c.user_email,
            table['scim_resource'].c.alias_email,
        ).order_by(table['scim_resource'].c.id)).all() == [
            ('admin@example.com', 'User', 'admin@example.com', None),
            (
                'member@b\u00fccher.example',
                'User',
                'member@xn--bcher-kva.example',
                None,
            ),
        ]
        assert connection.execute(sa.select(table['scim_state'])).all() == [
            (1, 0),
        ]
        assert connection.scalar(sa.select(sa.func.count()).select_from(
            table['scim_group_member']
        )) == 0
        assert connection.scalar(sa.select(sa.func.count()).select_from(
            table['scim_group_destination']
        )) == 0

        tombstones = [
            {
                'id': resource_id,
                'resource_type': 'Group',
                'external_id_bytes': None,
                'user_email': None,
                'alias_email': None,
                'subject_address': f'{resource_id}@outside.example',
                'deleted_at': datetime(2024, 1, 9),
                'created_at': date(2024, 1, 9),
                'updated_at': None,
                'comment': '',
            }
            for resource_id in ('Case-ID', 'case-id')
        ]
        connection.execute(table['scim_resource'].insert(), tombstones)
        assert set(connection.execute(
            sa.select(table['scim_resource'].c.id).where(
                table['scim_resource'].c.id.in_(['Case-ID', 'case-id'])
            )
        ).scalars()) == {'Case-ID', 'case-id'}

        if engine.dialect.name in MYSQL_FAMILY:
            rows = connection.execute(sa.text(
                """
                SELECT TABLE_NAME, COLUMN_NAME, CHARACTER_SET_NAME,
                       COLLATION_NAME
                  FROM information_schema.COLUMNS
                 WHERE TABLE_SCHEMA = DATABASE()
                   AND (
                     (TABLE_NAME = 'user' AND COLUMN_NAME IN
                       ('email', 'address_type')) OR
                     (TABLE_NAME = 'alias' AND COLUMN_NAME IN
                       ('email', 'address_type')) OR
                     (TABLE_NAME = 'mail_address' AND COLUMN_NAME IN
                       ('email', 'address_type')) OR
                     (TABLE_NAME = 'scim_resource' AND COLUMN_NAME IN
                       ('user_email', 'alias_email', 'subject_address', 'id')) OR
                     (TABLE_NAME = 'scim_group_member' AND COLUMN_NAME IN
                       ('group_id', 'member_id')) OR
                     (TABLE_NAME = 'scim_group_destination' AND COLUMN_NAME IN
                       ('group_id', 'destination'))
                   )
                """
            )).all()
            storage = {
                (table_name, column_name): (character_set, collation)
                for table_name, column_name, character_set, collation in rows
            }
            routing_columns = {
                ('user', 'email'),
                ('alias', 'email'),
                ('mail_address', 'email'),
                ('scim_resource', 'user_email'),
                ('scim_resource', 'alias_email'),
                ('scim_resource', 'subject_address'),
                ('scim_group_destination', 'destination'),
            }
            address_type_columns = {
                ('user', 'address_type'),
                ('alias', 'address_type'),
                ('mail_address', 'address_type'),
            }
            exact_columns = {
                ('scim_resource', 'id'),
                ('scim_group_member', 'group_id'),
                ('scim_group_member', 'member_id'),
                ('scim_group_destination', 'group_id'),
            }
            assert len({storage[column] for column in routing_columns}) == 1
            assert len({storage[column] for column in address_type_columns}) == 1
            exact_storage = {storage[column] for column in exact_columns}
            assert len(exact_storage) == 1
            _character_set, exact_collation = next(iter(exact_storage))
            assert exact_collation.endswith('_bin')
            model_type = models.ScimResource.__table__.c.id.type.dialect_impl(
                engine.dialect
            )
            assert model_type.charset == _character_set
            assert model_type.collation == exact_collation
            assert changed_default is not None
            legacy_collation, database_default = changed_default
            assert legacy_collation != database_default
            assert storage[('user', 'email')][1] == legacy_collation


def test_real_populated_upgrade_preserves_data_and_native_constraints(
    native_migration_app,
):
    engine = models.db.engine
    _upgrade(BASE_REVISION)
    snapshots = _seed_populated_legacy_database(engine)
    changed_default = _change_mysql_database_default(engine)
    _upgrade('head')
    _assert_populated_upgrade(engine, changed_default, snapshots)


def test_mysql_registry_storage_preflight_is_before_ddl(
    native_migration_app,
):
    engine = models.db.engine
    if engine.dialect.name not in MYSQL_FAMILY:
        pytest.skip('requires MariaDB/MySQL non-transactional DDL')

    _upgrade(BASE_REVISION)
    snapshots = _seed_populated_legacy_database(engine)
    original_collation, changed_collation = (
        _force_alias_email_collation_mismatch(engine)
    )
    assert original_collation != changed_collation

    with pytest.raises(RuntimeError, match='different email storage semantics'):
        _upgrade('head')

    inspector = sa.inspect(engine)
    table_names = set(inspector.get_table_names())
    assert 'mail_address' not in table_names
    assert not {name for name in table_names if name.startswith('scim_')}
    assert 'address_type' not in {
        column['name'] for column in inspector.get_columns('user')
    }
    assert 'address_type' not in {
        column['name'] for column in inspector.get_columns('alias')
    }
    assert 'auth_generation' not in {
        column['name'] for column in inspector.get_columns('user')
    }
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            'SELECT version_num FROM alembic_version'
        )) == BASE_REVISION
    _assert_table_snapshots(engine, snapshots)


def test_address_collision_preflight_retries_without_native_ddl(
    native_migration_app,
):
    engine = models.db.engine
    _upgrade(BASE_REVISION)
    snapshots = _seed_populated_legacy_database(engine)
    changed_default = _change_mysql_database_default(engine)
    with engine.begin() as connection:
        table = _tables(connection, 'alias')
        connection.execute(
            table['alias'].update()
            .where(table['alias'].c.email == 'list@example.com')
            .values(email='admin@example.com')
        )
        collision_snapshot = _snapshot_tables(
            connection,
            _tables(connection, *snapshots),
        )

    with pytest.raises(
        RuntimeError,
        match='admin@example.com: User=admin@example.com, '
        'Alias=admin@example.com',
    ):
        _upgrade(ADDRESS_REVISION)

    inspector = sa.inspect(engine)
    table_names = set(inspector.get_table_names())
    assert 'mail_address' not in table_names
    assert not {name for name in table_names if name.startswith('scim_')}
    assert 'address_type' not in {
        column['name'] for column in inspector.get_columns('user')
    }
    assert 'address_type' not in {
        column['name'] for column in inspector.get_columns('alias')
    }
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            'SELECT version_num FROM alembic_version'
        )) == BASE_REVISION
    _assert_table_snapshots(engine, collision_snapshot)

    with engine.begin() as connection:
        table = _tables(connection, 'alias')
        connection.execute(
            table['alias'].update()
            .where(table['alias'].c.email == 'admin@example.com')
            .values(email='list@example.com')
        )

    _upgrade('head')
    _assert_populated_upgrade(engine, changed_default, snapshots)


def test_invalid_legacy_identity_fails_before_identity_ddl_and_retries(
    native_migration_app,
):
    engine = models.db.engine
    _upgrade(BASE_REVISION)
    _seed_invalid_identity(engine)
    _upgrade(ADDRESS_REVISION)

    with pytest.raises(RuntimeError, match='invalid@xn--'):
        _upgrade('head')

    inspector = sa.inspect(engine)
    assert 'mail_address' in set(inspector.get_table_names())
    assert 'address_type' in {
        column['name'] for column in inspector.get_columns('user')
    }
    assert 'auth_generation' not in {
        column['name'] for column in inspector.get_columns('user')
    }
    assert not {
        'scim_state',
        'scim_resource',
        'scim_group_member',
        'scim_group_destination',
    } & set(inspector.get_table_names())
    with engine.begin() as connection:
        table = _tables(
            connection,
            'alembic_version',
            'user',
            'mail_address',
        )
        assert connection.scalar(
            sa.select(table['alembic_version'].c.version_num)
        ) == ADDRESS_REVISION
        connection.execute(
            table['user'].delete().where(
                table['user'].c.email == 'invalid@xn--'
            )
        )
        connection.execute(
            table['mail_address'].delete().where(
                table['mail_address'].c.email == 'invalid@xn--'
            )
        )

    _upgrade('head')
    inspector = sa.inspect(engine)
    assert 'auth_generation' in {
        column['name'] for column in inspector.get_columns('user')
    }
    _assert_member_index(inspector)
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            'SELECT COUNT(*) FROM scim_resource'
        )) == 0
        assert connection.scalar(sa.text(
            'SELECT version_num FROM alembic_version'
        )) == HEAD_REVISION


def test_postgresql_staging_sql_error_preserves_collision_diagnostic(
    native_migration_app,
):
    engine = models.db.engine
    if engine.dialect.name != 'postgresql':
        pytest.skip('requires PostgreSQL aborted-transaction behavior')

    _upgrade(BASE_REVISION)
    _seed_duplicate_published_identity(engine)
    _upgrade(ADDRESS_REVISION)

    with pytest.raises(
        RuntimeError,
        match='Cannot stage every legacy SCIM ID without loss or collision',
    ):
        _upgrade('head')

    inspector = sa.inspect(engine)
    assert 'auth_generation' not in {
        column['name'] for column in inspector.get_columns('user')
    }
    assert not {
        'scim_state',
        'scim_resource',
        'scim_group_member',
        'scim_group_destination',
    } & set(inspector.get_table_names())
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            'SELECT version_num FROM alembic_version'
        )) == ADDRESS_REVISION


def test_mysql_non_utf8mb4_legacy_schema_preserves_non_latin_scim_id(
    native_migration_app,
):
    engine = models.db.engine
    if engine.dialect.name not in MYSQL_FAMILY:
        pytest.skip('requires MariaDB/MySQL legacy charset storage')

    _set_mysql_database_default(engine, 'latin1', 'latin1_swedish_ci')
    _upgrade(BASE_REVISION)
    stored_email, published_id = _seed_non_latin_idna_identity(engine)
    _upgrade('head')

    with engine.connect() as connection:
        table = _tables(connection, 'scim_resource')
        assert connection.execute(sa.select(
            table['scim_resource'].c.id,
            table['scim_resource'].c.user_email,
        )).one() == (published_id, stored_email)
        assert _mysql_column_storage(
            connection,
            'user',
            'email',
        ) == ('latin1', 'latin1_swedish_ci')
        for table_name, column_name in (
            ('scim_resource', 'id'),
            ('scim_group_member', 'group_id'),
            ('scim_group_member', 'member_id'),
            ('scim_group_destination', 'group_id'),
        ):
            assert _mysql_column_storage(
                connection,
                table_name,
                column_name,
            ) == ('utf8mb4', 'utf8mb4_bin')

    model_type = models.ScimResource.__table__.c.id.type.dialect_impl(
        engine.dialect
    )
    assert model_type.charset == 'utf8mb4'
    assert model_type.collation == 'utf8mb4_bin'


def test_user_migration_reads_and_writes_are_bounded(
    native_migration_app,
    monkeypatch,
):
    engine = models.db.engine

    user_count = EXPECTED_BACKFILL_BATCH_SIZE + 1
    _upgrade(BASE_REVISION)
    _seed_backfill_population(
        engine,
        user_count,
        alias_count=user_count,
    )

    collision_probe_limits = []
    source_read_limits = []
    staged_batch_sizes = []
    copied_batch_sizes = []
    original_execute = sa.engine.Connection.execute

    def record_execute(
        connection,
        statement,
        parameters=None,
        *args,
        **kwargs,
    ):
        table = getattr(statement, 'table', None)
        table_name = getattr(table, 'name', None)
        if table_name == '_mailu_scim_resource_stage':
            staged_batch_sizes.append(
                len(parameters) if isinstance(parameters, list) else 1
            )
        elif table_name == 'scim_resource':
            copied_batch_sizes.append(
                len(parameters) if isinstance(parameters, list) else 1
            )

        get_final_froms = getattr(statement, 'get_final_froms', None)
        limit_clause = getattr(statement, '_limit_clause', None)
        if get_final_froms is not None and limit_clause is not None:
            from_names = {
                element.name
                for element in sa.sql.visitors.iterate(statement)
                if isinstance(element, sa.Table)
            }
            if from_names == {'alias', 'user'}:
                collision_probe_limits.append(limit_clause.value)
            if from_names == {'user'}:
                source_read_limits.append(limit_clause.value)
        return original_execute(
            connection,
            statement,
            parameters,
            *args,
            **kwargs,
        )

    monkeypatch.setattr(sa.engine.Connection, 'execute', record_execute)
    _upgrade(ADDRESS_REVISION)
    _upgrade('head')

    assert collision_probe_limits == [EXPECTED_COLLISION_PROBE_LIMIT] * 2
    assert source_read_limits == [EXPECTED_BACKFILL_BATCH_SIZE] * 3
    assert staged_batch_sizes == [EXPECTED_BACKFILL_BATCH_SIZE, 1]
    assert copied_batch_sizes == [EXPECTED_BACKFILL_BATCH_SIZE, 1]
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            'SELECT COUNT(*) FROM scim_resource'
        )) == user_count
