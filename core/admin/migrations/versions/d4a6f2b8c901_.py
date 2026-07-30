"""Enforce global User/Alias routing-address uniqueness

Revision ID: d4a6f2b8c901
Revises: 9a5866105f5a
Create Date: 2026-07-29 14:00:00.000000

User and Alias historically had independent email primary keys. A shared
mail_address registry now serializes ownership of a canonical routing address.
Existing cross-table collisions are ambiguous operator data, so the migration
refuses to mutate the schema until an administrator resolves them.
"""

# revision identifiers, used by Alembic.
revision = 'd4a6f2b8c901'
down_revision = '9a5866105f5a'

from alembic import op
import sqlalchemy as sa


naming_convention = {
    'fk': '%(table_name)s_%(column_0_name)s_fkey',
    'pk': '%(table_name)s_pkey',
}

metadata = sa.MetaData()
user = sa.Table(
    'user',
    metadata,
    sa.Column('email', sa.String(255), primary_key=True),
)
alias = sa.Table(
    'alias',
    metadata,
    sa.Column('email', sa.String(255), primary_key=True),
)
mail_address = sa.Table(
    'mail_address',
    metadata,
    sa.Column('email', sa.String(255), primary_key=True),
    sa.Column('address_type', sa.String(5), nullable=False),
)


def _registry_string_types(connection):
    """Match the existing routing-key collation before creating the registry.

    MariaDB/MySQL do not permit a foreign key between string columns whose
    character set or collation differs.  More importantly, creating the new
    table with the *database's current* default can make the registry compare
    addresses more broadly than the existing User/Alias primary keys.  That
    turns an otherwise valid populated upgrade into a non-transactional,
    half-applied migration.
    """
    if connection.dialect.name != 'mysql':
        return sa.String(length=255), sa.String(length=5)

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
    if len(rows) != 2:
        raise RuntimeError(
            'Cannot inspect both User and Alias email column collations '
            'before creating the global mail-address registry.'
        )
    storage = {
        (character_set, collation)
        for _table, character_set, collation in rows
    }
    if len(storage) != 1:
        details = ', '.join(
            f'{table}={character_set}/{collation}'
            for table, character_set, collation in sorted(rows)
        )
        raise RuntimeError(
            'Cannot enforce global mail-address uniqueness because User and '
            f'Alias use different email storage semantics: {details}. '
            'Align the columns, then retry.'
        )
    character_set, collation = storage.pop()
    if not character_set or not collation:
        raise RuntimeError(
            'Cannot determine the User/Alias email storage collation before '
            'creating the global mail-address registry.'
        )
    return (
        sa.String(length=255, collation=collation),
        sa.String(length=5, collation=collation),
    )


def _cross_table_collisions(connection):
    users = {
        email.lower(): email
        for (email,) in connection.execute(sa.select(user.c.email))
    }
    aliases = {
        email.lower(): email
        for (email,) in connection.execute(sa.select(alias.c.email))
    }
    collisions = {
        (users[canonical], aliases[canonical]): canonical
        for canonical in users.keys() & aliases.keys()
    }

    # The application canonicalizer catches case/IDNA aliases.  MariaDB may
    # use a still-broader accent-insensitive collation, so also ask the target
    # database which values compare equal before creating any DDL.
    native_pairs = connection.execute(
        sa.select(user.c.email, alias.c.email).select_from(
            user.join(alias, user.c.email == alias.c.email)
        )
    )
    for user_email, alias_email in native_pairs:
        collisions.setdefault(
            (user_email, alias_email),
            user_email.lower(),
        )

    return [
        (canonical, user_email, alias_email)
        for (user_email, alias_email), canonical in sorted(
            collisions.items(),
            key=lambda item: (item[1], item[0]),
        )
    ]


def _requires_sqlite_reference_rebuild(connection):
    """SQLite table copies require inbound FK removal; native ALTER does not."""
    return connection.dialect.name == 'sqlite'


def _drop_user_references():
    with op.batch_alter_table(
        'alias',
        naming_convention=naming_convention,
    ) as batch:
        batch.drop_constraint(
            'alias_owner_email_fkey',
            type_='foreignkey',
        )
    with op.batch_alter_table(
        'fetch',
        naming_convention=naming_convention,
    ) as batch:
        batch.drop_constraint(
            'fetch_user_email_fkey',
            type_='foreignkey',
        )
    with op.batch_alter_table(
        'token',
        naming_convention=naming_convention,
    ) as batch:
        batch.drop_constraint(
            'token_user_email_fkey',
            type_='foreignkey',
        )
    with op.batch_alter_table(
        'manager',
        naming_convention=naming_convention,
    ) as batch:
        batch.drop_constraint(
            'manager_user_email_fkey',
            type_='foreignkey',
        )
    with op.batch_alter_table(
        'domain_access',
        naming_convention=naming_convention,
    ) as batch:
        batch.drop_constraint(
            'domain_access_user_email_fkey',
            type_='foreignkey',
        )


def _restore_user_references():
    with op.batch_alter_table(
        'alias',
        naming_convention=naming_convention,
    ) as batch:
        batch.create_foreign_key(
            'alias_owner_email_fkey',
            'user',
            ['owner_email'],
            ['email'],
        )
    with op.batch_alter_table(
        'fetch',
        naming_convention=naming_convention,
    ) as batch:
        batch.create_foreign_key(
            'fetch_user_email_fkey',
            'user',
            ['user_email'],
            ['email'],
        )
    with op.batch_alter_table(
        'token',
        naming_convention=naming_convention,
    ) as batch:
        batch.create_foreign_key(
            'token_user_email_fkey',
            'user',
            ['user_email'],
            ['email'],
        )
    with op.batch_alter_table(
        'manager',
        naming_convention=naming_convention,
    ) as batch:
        batch.create_foreign_key(
            'manager_user_email_fkey',
            'user',
            ['user_email'],
            ['email'],
        )
    with op.batch_alter_table(
        'domain_access',
        naming_convention=naming_convention,
    ) as batch:
        batch.create_foreign_key(
            'domain_access_user_email_fkey',
            'user',
            ['user_email'],
            ['email'],
        )


def upgrade():
    connection = op.get_bind()

    # MySQL/MariaDB may auto-commit DDL, so this destructive ambiguity check
    # must remain the first operation.
    registry_email_type, registry_address_type = _registry_string_types(
        connection
    )
    collisions = _cross_table_collisions(connection)
    if collisions:
        listing = '\n'.join(
            f'  {canonical}: User={user_email}, Alias={alias_email}'
            for canonical, user_email, alias_email in collisions
        )
        raise RuntimeError(
            'Cannot enforce global mail-address uniqueness. These addresses '
            'exist as both User and Alias:\n'
            f'{listing}\n'
            'Remove or rename one owner of each address, then retry.'
        )

    op.create_table(
        'mail_address',
        sa.Column('email', registry_email_type, nullable=False),
        sa.Column('address_type', registry_address_type, nullable=False),
        sa.CheckConstraint(
            "address_type IN ('user', 'alias')",
            name='mail_address_type_check',
        ),
        sa.PrimaryKeyConstraint(
            'email',
            name='mail_address_pkey',
        ),
        sa.UniqueConstraint(
            'email',
            'address_type',
            name='mail_address_email_type_key',
        ),
    )

    connection.execute(
        mail_address.insert().from_select(
            ['email', 'address_type'],
            sa.select(
                user.c.email,
                sa.literal('user'),
            ),
        )
    )
    connection.execute(
        mail_address.insert().from_select(
            ['email', 'address_type'],
            sa.select(
                alias.c.email,
                sa.literal('alias'),
            ),
        )
    )

    rebuild_references = _requires_sqlite_reference_rebuild(connection)
    if rebuild_references:
        _drop_user_references()

    with op.batch_alter_table(
        'user',
        naming_convention=naming_convention,
    ) as batch:
        batch.add_column(
            sa.Column(
                'address_type',
                registry_address_type,
                nullable=False,
                server_default='user',
            )
        )
        batch.create_check_constraint(
            'user_address_type_check',
            "address_type = 'user'",
        )
        batch.create_foreign_key(
            'user_mail_address_fkey',
            'mail_address',
            ['email', 'address_type'],
            ['email', 'address_type'],
        )

    with op.batch_alter_table(
        'alias',
        naming_convention=naming_convention,
    ) as batch:
        batch.add_column(
            sa.Column(
                'address_type',
                registry_address_type,
                nullable=False,
                server_default='alias',
            )
        )
        batch.create_check_constraint(
            'alias_address_type_check',
            "address_type = 'alias'",
        )
        batch.create_foreign_key(
            'alias_mail_address_fkey',
            'mail_address',
            ['email', 'address_type'],
            ['email', 'address_type'],
        )

    if rebuild_references:
        _restore_user_references()

    expected = connection.scalar(
        sa.select(sa.func.count()).select_from(user)
    ) + connection.scalar(
        sa.select(sa.func.count()).select_from(alias)
    )
    actual = connection.scalar(
        sa.select(sa.func.count()).select_from(mail_address)
    )
    if actual != expected:
        raise RuntimeError(
            f'mail_address backfill count mismatch: expected {expected}, '
            f'found {actual}'
        )


def downgrade():
    connection = op.get_bind()
    rebuild_references = _requires_sqlite_reference_rebuild(connection)
    if rebuild_references:
        _drop_user_references()

    with op.batch_alter_table(
        'user',
        naming_convention=naming_convention,
    ) as batch:
        batch.drop_constraint(
            'user_mail_address_fkey',
            type_='foreignkey',
        )
        batch.drop_constraint(
            'user_address_type_check',
            type_='check',
        )
        batch.drop_column('address_type')

    with op.batch_alter_table(
        'alias',
        naming_convention=naming_convention,
    ) as batch:
        batch.drop_constraint(
            'alias_mail_address_fkey',
            type_='foreignkey',
        )
        batch.drop_constraint(
            'alias_address_type_check',
            type_='check',
        )
        batch.drop_column('address_type')

    if rebuild_references:
        _restore_user_references()
    op.drop_table('mail_address')
