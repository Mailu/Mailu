"""Add persistent SCIM identity, graph state, and session authority

Revision ID: e7c9a4f2b631
Revises: d4a6f2b8c901
Create Date: 2026-07-29 14:30:00.000000

Existing Users retain their published email IDs and receive the all-zero
migration generation.  Existing Aliases are deliberately not adopted as
Groups.  New application-created Users receive random generations and UUID
SCIM mappings at the model boundary.
"""

# revision identifiers, used by Alembic.
revision = 'e7c9a4f2b631'
down_revision = 'd4a6f2b8c901'

from datetime import date

from alembic import op
import idna
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


INITIAL_AUTH_GENERATION = '0' * 32
SCIM_BACKFILL_BATCH_SIZE = 128
MYSQL_EXACT_ID_CHARSET = 'utf8mb4'
MYSQL_EXACT_ID_COLLATION = 'utf8mb4_bin'
STAGING_TABLE_NAME = '_mailu_scim_resource_stage'

metadata = sa.MetaData()
user = sa.Table(
    'user',
    metadata,
    sa.Column('email', sa.String(255), primary_key=True),
    sa.Column('created_at', sa.Date, nullable=False),
    sa.Column('updated_at', sa.Date, nullable=True),
)
scim_resource = sa.Table(
    'scim_resource',
    metadata,
    sa.Column('id', sa.String(255), primary_key=True),
    sa.Column('resource_type', sa.String(5), nullable=False),
    sa.Column('external_id_bytes', sa.LargeBinary(1024), nullable=True),
    sa.Column('user_email', sa.String(255), nullable=True),
    sa.Column('alias_email', sa.String(255), nullable=True),
    sa.Column('subject_address', sa.String(255), nullable=False),
    sa.Column('deleted_at', sa.DateTime, nullable=True),
    sa.Column('created_at', sa.Date, nullable=False),
    sa.Column('updated_at', sa.Date, nullable=True),
    sa.Column('comment', sa.String(255), nullable=True),
)


def _published_email_id(stored_email):
    """Reproduce IdnaEmail's externally published Unicode representation."""
    localpart, domain_name = stored_email.lower().rsplit('@', 1)
    return f'{localpart}@{idna.decode(domain_name)}'


def _x_arguments():
    arguments = op.get_context().opts.get('x_argument') or []
    parsed = {}
    for argument in arguments:
        key, separator, value = argument.partition('=')
        parsed[key] = value if separator else 'true'
    return parsed


def _destructive_downgrade_allowed():
    arguments = _x_arguments()
    return (
        arguments.get('allow_destructive_scim_identity', '').lower()
        in ('1', 'true', 'yes')
        and arguments.get('scim_identity_exported', '').lower()
        in ('1', 'true', 'yes')
    )


def _storage_types(connection):
    """Resolve routing-key and byte-exact provider-ID storage types."""
    if connection.dialect.name not in {'mysql', 'mariadb'}:
        return sa.String(length=255), sa.String(length=255)

    rows = connection.execute(
        sa.text(
            """
            SELECT TABLE_NAME, CHARACTER_SET_NAME, COLLATION_NAME
              FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE()
               AND TABLE_NAME IN ('user', 'alias')
               AND COLUMN_NAME = 'email'
            """
        )
    ).all()
    storage = {
        (character_set, collation)
        for _table, character_set, collation in rows
    }
    if len(rows) != 2 or len(storage) != 1:
        details = ', '.join(
            f'{table}={character_set}/{collation}'
            for table, character_set, collation in sorted(rows)
        )
        raise RuntimeError(
            'Cannot create SCIM identity foreign keys because User and Alias '
            f'email storage semantics differ or are unavailable: {details}.'
        )
    character_set, collation = storage.pop()
    if not collation:
        raise RuntimeError(
            'Cannot determine the User/Alias email collation before creating '
            'SCIM identity tables.'
        )
    exact_collation = connection.scalar(
        sa.text(
            """
            SELECT COLLATION_NAME
              FROM information_schema.COLLATIONS
             WHERE CHARACTER_SET_NAME = :character_set
               AND COLLATION_NAME = :collation
            """
        ),
        {
            'character_set': MYSQL_EXACT_ID_CHARSET,
            'collation': MYSQL_EXACT_ID_COLLATION,
        },
    )
    if exact_collation is None:
        raise RuntimeError(
            'Cannot find the required utf8mb4_bin collation for exact SCIM '
            'provider IDs.'
        )
    return (
        mysql.VARCHAR(
            length=255,
            charset=character_set,
            collation=collation,
        ),
        mysql.VARCHAR(
            length=255,
            charset=MYSQL_EXACT_ID_CHARSET,
            collation=exact_collation,
        ),
    )


def _staging_table(routing_email_type, exact_id_type):
    return sa.Table(
        STAGING_TABLE_NAME,
        sa.MetaData(),
        sa.Column('id', exact_id_type, primary_key=True),
        sa.Column('resource_type', sa.String(5), nullable=False),
        sa.Column('external_id_bytes', sa.LargeBinary(1024), nullable=True),
        sa.Column('user_email', routing_email_type, nullable=True),
        sa.Column('alias_email', routing_email_type, nullable=True),
        sa.Column('subject_address', routing_email_type, nullable=False),
        sa.Column('deleted_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.Date, nullable=False),
        sa.Column('updated_at', sa.Date, nullable=True),
        sa.Column('comment', sa.String(255), nullable=True),
        prefixes=['TEMPORARY'],
    )


def _drop_staging_table(connection):
    if connection.dialect.name in {'mysql', 'mariadb'}:
        connection.exec_driver_sql(
            f'DROP TEMPORARY TABLE IF EXISTS {STAGING_TABLE_NAME}'
        )
    else:
        connection.exec_driver_sql(
            f'DROP TABLE IF EXISTS {STAGING_TABLE_NAME}'
        )


def _prepare_user_resource(email, created_at, updated_at):
    try:
        resource_id = _published_email_id(email)
    except (idna.IDNAError, UnicodeError, ValueError) as exc:
        raise RuntimeError(
            f'Cannot publish a SCIM ID for legacy User {email!r}: {exc}'
        ) from exc
    if len(resource_id) > 255:
        raise RuntimeError(
            f'Published SCIM ID for legacy User {email!r} exceeds '
            '255 characters'
        )
    return {
        'id': resource_id,
        'resource_type': 'User',
        'external_id_bytes': None,
        'user_email': email,
        'alias_email': None,
        'subject_address': email,
        'deleted_at': None,
        'created_at': created_at or date.today(),
        'updated_at': updated_at,
        'comment': '',
    }


def _stage_user_resources(connection, routing_email_type, exact_id_type):
    """Validate and stage legacy identities in population-independent memory."""
    staging = _staging_table(routing_email_type, exact_id_type)
    staging.create(connection)
    last_email = None
    try:
        while True:
            query = sa.select(
                user.c.email,
                user.c.created_at,
                user.c.updated_at,
            ).order_by(user.c.email).limit(SCIM_BACKFILL_BATCH_SIZE)
            if last_email is not None:
                query = query.where(user.c.email > last_email)
            rows = connection.execute(query).all()
            if not rows:
                break

            prepared = [
                _prepare_user_resource(email, created_at, updated_at)
                for email, created_at, updated_at in rows
            ]
            connection.execute(staging.insert(), prepared)

            expected = {item['id'] for item in prepared}
            stored = set(connection.execute(
                sa.select(staging.c.id).where(staging.c.id.in_(expected))
            ).scalars())
            if stored != expected:
                raise RuntimeError(
                    'Exact SCIM ID storage is not a lossless round trip'
                )
            last_email = rows[-1][0]
    except sa.exc.SQLAlchemyError as exc:
        # PostgreSQL rejects cleanup SQL after a statement aborts the
        # transaction. Alembic closes this NullPool connection on failure, so
        # the temporary table is discarded without masking the real error.
        raise RuntimeError(
            'Cannot stage every legacy SCIM ID without loss or collision'
        ) from exc
    except Exception:
        _drop_staging_table(connection)
        raise
    return staging


def _copy_staged_user_resources(connection, staging):
    column_names = [column.name for column in scim_resource.columns]
    last_id = None
    while True:
        query = sa.select(*(
            staging.c[name] for name in column_names
        )).order_by(staging.c.id).limit(SCIM_BACKFILL_BATCH_SIZE)
        if last_id is not None:
            query = query.where(staging.c.id > last_id)
        rows = connection.execute(query).mappings().all()
        if not rows:
            return
        connection.execute(
            scim_resource.insert(),
            [dict(row) for row in rows],
        )
        last_id = rows[-1]['id']


def upgrade():
    connection = op.get_bind()
    routing_email_type, exact_id_type = _storage_types(connection)
    staged_users = _stage_user_resources(
        connection,
        routing_email_type,
        exact_id_type,
    )

    with op.batch_alter_table('user') as batch:
        batch.add_column(
            sa.Column(
                'auth_generation',
                sa.String(length=32),
                nullable=False,
                server_default=INITIAL_AUTH_GENERATION,
            )
        )

    op.create_table(
        'scim_state',
        sa.Column(
            'id',
            sa.Integer(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            'revision',
            sa.BigInteger(),
            nullable=False,
            server_default='0',
        ),
        sa.CheckConstraint('id = 1', name='scim_state_singleton_check'),
        sa.PrimaryKeyConstraint('id', name='scim_state_pkey'),
    )
    op.create_table(
        'scim_resource',
        sa.Column('id', exact_id_type, nullable=False),
        sa.Column('resource_type', sa.String(length=5), nullable=False),
        sa.Column(
            'external_id_bytes',
            sa.LargeBinary(length=1024),
            nullable=True,
        ),
        sa.Column('user_email', routing_email_type, nullable=True),
        sa.Column('alias_email', routing_email_type, nullable=True),
        sa.Column('subject_address', routing_email_type, nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.Date(), nullable=True),
        sa.Column(
            'comment',
            sa.String(length=255),
            nullable=True,
            server_default='',
        ),
        sa.CheckConstraint(
            "resource_type IN ('User', 'Group')",
            name='scim_resource_type_check',
        ),
        sa.CheckConstraint(
            '('
            "deleted_at IS NULL AND resource_type = 'User' "
            'AND user_email IS NOT NULL AND alias_email IS NULL '
            'AND subject_address = user_email'
            ') OR ('
            "deleted_at IS NULL AND resource_type = 'Group' "
            'AND user_email IS NULL AND alias_email IS NOT NULL '
            'AND subject_address = alias_email'
            ') OR ('
            'deleted_at IS NOT NULL '
            'AND user_email IS NULL AND alias_email IS NULL'
            ')',
            name='scim_resource_lifecycle_check',
        ),
        sa.ForeignKeyConstraint(
            ['user_email'],
            ['user.email'],
            name='scim_resource_user_email_fkey',
        ),
        sa.ForeignKeyConstraint(
            ['alias_email'],
            ['alias.email'],
            name='scim_resource_alias_email_fkey',
        ),
        sa.PrimaryKeyConstraint('id', name='scim_resource_pkey'),
        sa.UniqueConstraint(
            'user_email',
            name='scim_resource_user_email_key',
        ),
        sa.UniqueConstraint(
            'alias_email',
            name='scim_resource_alias_email_key',
        ),
    )
    op.create_table(
        'scim_group_member',
        sa.Column('group_id', exact_id_type, nullable=False),
        sa.Column('member_id', exact_id_type, nullable=False),
        sa.ForeignKeyConstraint(
            ['group_id'],
            ['scim_resource.id'],
            name='scim_group_member_group_id_fkey',
        ),
        sa.ForeignKeyConstraint(
            ['member_id'],
            ['scim_resource.id'],
            name='scim_group_member_member_id_fkey',
        ),
        sa.PrimaryKeyConstraint(
            'group_id',
            'member_id',
            name='scim_group_member_pkey',
        ),
    )
    op.create_index(
        'scim_group_member_member_id_idx',
        'scim_group_member',
        ['member_id'],
    )
    op.create_table(
        'scim_group_destination',
        sa.Column('group_id', exact_id_type, nullable=False),
        sa.Column('destination', routing_email_type, nullable=False),
        sa.ForeignKeyConstraint(
            ['group_id'],
            ['scim_resource.id'],
            name='scim_group_destination_group_id_fkey',
        ),
        sa.PrimaryKeyConstraint(
            'group_id',
            'destination',
            name='scim_group_destination_pkey',
        ),
    )
    op.create_index(
        'scim_group_destination_destination_idx',
        'scim_group_destination',
        ['destination'],
    )

    connection.execute(
        sa.text(
            'INSERT INTO scim_state (id, revision) VALUES (1, 0)'
        )
    )

    _copy_staged_user_resources(connection, staged_users)

    expected_users = connection.scalar(
        sa.select(sa.func.count()).select_from(user)
    )
    actual_users = connection.scalar(
        sa.select(sa.func.count()).select_from(scim_resource).where(
            scim_resource.c.resource_type == 'User'
        )
    )
    actual_groups = connection.scalar(
        sa.select(sa.func.count()).select_from(scim_resource).where(
            scim_resource.c.resource_type == 'Group'
        )
    )
    if actual_users != expected_users or actual_groups != 0:
        raise RuntimeError(
            'SCIM identity backfill mismatch: '
            f'expected {expected_users} Users/0 Groups, found '
            f'{actual_users} Users/{actual_groups} Groups'
        )

    # Zero is a migration compatibility marker, never the ORM default for a
    # new principal.  Native ALTER can drop the temporary server default
    # without rebuilding User.  SQLite retains it only for unsupported raw
    # INSERTs; every supported ORM writer supplies a random generation.
    if connection.dialect.name != 'sqlite':
        op.alter_column(
            'user',
            'auth_generation',
            existing_type=sa.String(length=32),
            nullable=False,
            server_default=None,
        )
    _drop_staging_table(connection)


def downgrade():
    connection = op.get_bind()
    identity_count = connection.scalar(
        sa.select(sa.func.count()).select_from(scim_resource)
    )
    if identity_count and not _destructive_downgrade_allowed():
        raise RuntimeError(
            'Refusing destructive SCIM identity downgrade. Complete an '
            'identity export including tombstone data, then pass both '
            '-x allow_destructive_scim_identity=true and '
            '-x scim_identity_exported=true.'
        )

    op.drop_table('scim_group_destination')
    op.drop_table('scim_group_member')
    op.drop_table('scim_resource')
    op.drop_table('scim_state')
    if connection.dialect.name == 'sqlite':
        op.drop_column('user', 'auth_generation')
    else:
        with op.batch_alter_table('user') as batch:
            batch.drop_column('auth_generation')
