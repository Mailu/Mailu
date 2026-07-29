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


INITIAL_AUTH_GENERATION = '0' * 32

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
    if connection.dialect.name != 'mysql':
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
    binary_collation = connection.scalar(
        sa.text(
            """
            SELECT COLLATION_NAME
              FROM information_schema.COLLATIONS
             WHERE CHARACTER_SET_NAME = :character_set
               AND COLLATION_NAME = :collation
            """
        ),
        {
            'character_set': character_set,
            'collation': f'{character_set}_bin',
        },
    )
    if binary_collation is None:
        raise RuntimeError(
            'Cannot find a binary collation for exact SCIM provider IDs '
            f'in character set {character_set!r}.'
        )
    return (
        sa.String(length=255, collation=collation),
        sa.String(length=255, collation=binary_collation),
    )


def upgrade():
    connection = op.get_bind()
    routing_email_type, exact_id_type = _storage_types(connection)

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

    rows = connection.execute(
        sa.select(
            user.c.email,
            user.c.created_at,
            user.c.updated_at,
        ).order_by(user.c.email)
    ).all()
    for email, created_at, updated_at in rows:
        connection.execute(
            scim_resource.insert().values(
                id=_published_email_id(email),
                resource_type='User',
                external_id_bytes=None,
                user_email=email,
                alias_email=None,
                subject_address=email,
                deleted_at=None,
                created_at=created_at or date.today(),
                updated_at=updated_at,
                comment='',
            )
        )

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
