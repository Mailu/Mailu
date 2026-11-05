"""Add OAuth authorization codes, grants, and refresh-token history.

Grant identifiers are random and stable so derived tokens remain unique even
after their grant rows have been deleted and a database reuses a primary key.

Revision ID: ab6f4e2c91d0
Revises: ea12b9426c7f
Create Date: 2026-11-04
"""

import secrets
import time

from alembic import op
import sqlalchemy as sa


revision = 'ab6f4e2c91d0'
down_revision = 'ea12b9426c7f'
branch_labels = None
depends_on = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table_name):
    return {index['name'] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_authorization_codes():
    if 'oauth2_authorization_code' not in _tables():
        op.create_table(
            'oauth2_authorization_code',
            sa.Column('code_hash', sa.String(length=64), primary_key=True),
            sa.Column('user_email', sa.String(length=255), nullable=False),
            sa.Column('client_id', sa.String(length=80), nullable=False),
            sa.Column('redirect_uri', sa.String(length=2048), nullable=False),
            sa.Column('scope', sa.String(length=255), nullable=False),
            sa.Column('code_challenge', sa.String(length=128), nullable=False),
            sa.Column('expires_at', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.Date(), server_default=sa.func.current_date(), nullable=False),
            sa.Column('updated_at', sa.Date(), nullable=True),
            sa.Column('comment', sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(['user_email'], ['user.email'], ondelete='CASCADE'),
        )
    indexes = _indexes('oauth2_authorization_code')
    if 'ix_oauth2_authorization_code_user_email' not in indexes:
        op.create_index(
            'ix_oauth2_authorization_code_user_email',
            'oauth2_authorization_code', ['user_email'], unique=False,
        )
    if 'ix_oauth2_authorization_code_expires_at' not in indexes:
        op.create_index(
            'ix_oauth2_authorization_code_expires_at',
            'oauth2_authorization_code', ['expires_at'], unique=False,
        )


def _create_grants():
    if 'oauth2_grant' not in _tables():
        op.create_table(
            'oauth2_grant',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('grant_id', sa.String(length=22), nullable=False),
            sa.Column('user_email', sa.String(length=255), nullable=False),
            sa.Column('client_id', sa.String(length=80), nullable=False),
            sa.Column('token_generation', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('scope', sa.String(length=255), nullable=False),
            sa.Column('access_expires_at', sa.Integer(), nullable=False),
            sa.Column('refresh_expires_at', sa.Integer(), nullable=True),
            sa.Column('client_name', sa.String(length=120), nullable=False, server_default='Mail app'),
            sa.Column('last_refresh_at', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.Date(), server_default=sa.func.current_date(), nullable=False),
            sa.Column('updated_at', sa.Date(), nullable=True),
            sa.Column('comment', sa.String(length=255), nullable=True),
            sa.UniqueConstraint('grant_id', name='uq_oauth2_grant_grant_id'),
            sa.ForeignKeyConstraint(['user_email'], ['user.email'], ondelete='CASCADE'),
        )
    else:
        columns = {column['name']: column for column in sa.inspect(op.get_bind()).get_columns('oauth2_grant')}
        missing_columns = (
            ('token_generation', sa.Column('token_generation', sa.Integer(), nullable=False, server_default='0')),
            ('client_name', sa.Column('client_name', sa.String(length=120), nullable=False, server_default='Mail app')),
            ('last_refresh_at', sa.Column('last_refresh_at', sa.Integer(), nullable=True)),
        )
        for name, column in missing_columns:
            if name not in columns:
                op.add_column('oauth2_grant', column)

        if 'grant_id' not in columns:
            op.add_column(
                'oauth2_grant',
                sa.Column('grant_id', sa.String(length=22), nullable=True),
            )

        # Rotate legacy identifiers as this single migration evolves. Old token
        # formats are deliberately invalidated; preserve their rows for audit.
        connection = op.get_bind()
        grant_table = sa.table(
            'oauth2_grant',
            sa.column('id', sa.Integer()),
            sa.column('grant_id', sa.String(length=22)),
            sa.column('access_expires_at', sa.Integer()),
            sa.column('refresh_expires_at', sa.Integer()),
        )
        now = int(time.time())
        rows = connection.execute(sa.select(
            grant_table.c.id, grant_table.c.grant_id,
            grant_table.c.access_expires_at, grant_table.c.refresh_expires_at,
        )).mappings()
        for row in rows:
            if row['grant_id'] and len(row['grant_id']) == 22:
                continue
            connection.execute(
                grant_table.update().where(grant_table.c.id == row['id']).values(
                    grant_id=secrets.token_urlsafe(16),
                    access_expires_at=min(row['access_expires_at'], now),
                    refresh_expires_at=(
                        min(row['refresh_expires_at'], now)
                        if row['refresh_expires_at'] is not None else None
                    ),
                )
            )
        columns = {column['name']: column for column in sa.inspect(op.get_bind()).get_columns('oauth2_grant')}

        unique_constraints = {
            constraint.get('name')
            for constraint in sa.inspect(op.get_bind()).get_unique_constraints('oauth2_grant')
        }
        grant_id_type = columns['grant_id']['type']
        grant_id_nullable = columns['grant_id']['nullable']
        if (
            grant_id_nullable
            or getattr(grant_id_type, 'length', None) != 22
            or 'uq_oauth2_grant_grant_id' not in unique_constraints
        ):
            with op.batch_alter_table('oauth2_grant') as batch:
                if grant_id_nullable or getattr(grant_id_type, 'length', None) != 22:
                    batch.alter_column(
                        'grant_id', existing_type=grant_id_type,
                        type_=sa.String(length=22),
                        existing_nullable=grant_id_nullable, nullable=False,
                    )
                if 'uq_oauth2_grant_grant_id' not in unique_constraints:
                    batch.create_unique_constraint('uq_oauth2_grant_grant_id', ['grant_id'])

        columns = {column['name']: column for column in sa.inspect(op.get_bind()).get_columns('oauth2_grant')}
        nullable_changes = [
            name for name in ('refresh_expires_at',)
            if name in columns and not columns[name]['nullable']
        ]
        if nullable_changes:
            with op.batch_alter_table('oauth2_grant') as batch:
                for name in nullable_changes:
                    existing_type = columns[name]['type']
                    batch.alter_column(
                        name, existing_type=existing_type,
                        existing_nullable=False, nullable=True,
                    )

    indexes = _indexes('oauth2_grant')
    for name, column in (
        ('ix_oauth2_grant_user_email', 'user_email'),
        ('ix_oauth2_grant_access_expires_at', 'access_expires_at'),
        ('ix_oauth2_grant_refresh_expires_at', 'refresh_expires_at'),
    ):
        if name not in indexes:
            op.create_index(name, 'oauth2_grant', [column], unique=False)


def upgrade():
    _create_authorization_codes()
    _create_grants()


def downgrade():
    tables = _tables()
    if 'oauth2_grant' in tables:
        indexes = _indexes('oauth2_grant')
        for name in (
            'ix_oauth2_grant_refresh_expires_at',
            'ix_oauth2_grant_access_expires_at',
            'ix_oauth2_grant_user_email',
        ):
            if name in indexes:
                op.drop_index(name, table_name='oauth2_grant')
        op.drop_table('oauth2_grant')
    if 'oauth2_authorization_code' in tables:
        indexes = _indexes('oauth2_authorization_code')
        for name in (
            'ix_oauth2_authorization_code_expires_at',
            'ix_oauth2_authorization_code_user_email',
        ):
            if name in indexes:
                op.drop_index(name, table_name='oauth2_authorization_code')
        op.drop_table('oauth2_authorization_code')
