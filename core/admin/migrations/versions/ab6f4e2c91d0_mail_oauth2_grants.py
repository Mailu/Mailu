"""Add OAuth authorization codes, grants, and refresh-token history.

Revision ID: ab6f4e2c91d0
Revises: ea12b9426c7f
Create Date: 2026-11-04
"""

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
            sa.Column('user_email', sa.String(length=255), nullable=False),
            sa.Column('client_id', sa.String(length=80), nullable=False),
            sa.Column('access_token_hash', sa.String(length=64), nullable=False, unique=True),
            sa.Column('refresh_token_hash', sa.String(length=64), nullable=True, unique=True),
            sa.Column('scope', sa.String(length=255), nullable=False),
            sa.Column('access_expires_at', sa.Integer(), nullable=False),
            sa.Column('refresh_expires_at', sa.Integer(), nullable=True),
            sa.Column('client_name', sa.String(length=120), nullable=False, server_default='Mail app'),
            sa.Column('last_refresh_at', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.Date(), server_default=sa.func.current_date(), nullable=False),
            sa.Column('updated_at', sa.Date(), nullable=True),
            sa.Column('comment', sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(['user_email'], ['user.email'], ondelete='CASCADE'),
        )
    else:
        columns = {column['name']: column for column in sa.inspect(op.get_bind()).get_columns('oauth2_grant')}
        missing_columns = (
            ('client_name', sa.Column('client_name', sa.String(length=120), nullable=False, server_default='Mail app')),
            ('last_refresh_at', sa.Column('last_refresh_at', sa.Integer(), nullable=True)),
        )
        for name, column in missing_columns:
            if name not in columns:
                op.add_column('oauth2_grant', column)

        columns = {column['name']: column for column in sa.inspect(op.get_bind()).get_columns('oauth2_grant')}
        nullable_changes = [
            name for name in ('refresh_token_hash', 'refresh_expires_at')
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


def _create_refresh_token_history():
    if 'oauth2_refresh_token_history' not in _tables():
        op.create_table(
            'oauth2_refresh_token_history',
            sa.Column('created_at', sa.Date(), server_default=sa.func.current_date(), nullable=False),
            sa.Column('updated_at', sa.Date(), nullable=True),
            sa.Column('comment', sa.String(length=255), nullable=True),
            sa.Column('token_hash', sa.String(length=64), primary_key=True),
            sa.Column('grant_id', sa.Integer(), nullable=False),
            sa.Column('used_at', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['grant_id'], ['oauth2_grant.id'], ondelete='CASCADE'),
        )
    else:
        # These columns come from the shared Base model. Earlier versions of
        # this squashed migration created the table without them; repair that
        # schema when upgrading an installation that already ran it.
        columns = {column['name']: column for column in sa.inspect(op.get_bind()).get_columns('oauth2_refresh_token_history')}
        if 'created_at' not in columns:
            op.add_column(
                'oauth2_refresh_token_history',
                sa.Column('created_at', sa.Date(), server_default=sa.func.current_date(), nullable=False),
            )
        if 'updated_at' not in columns:
            op.add_column('oauth2_refresh_token_history', sa.Column('updated_at', sa.Date(), nullable=True))
        if 'comment' not in columns:
            op.add_column('oauth2_refresh_token_history', sa.Column('comment', sa.String(length=255), nullable=True))
    if 'ix_oauth2_refresh_token_history_grant_id' not in _indexes('oauth2_refresh_token_history'):
        op.create_index(
            'ix_oauth2_refresh_token_history_grant_id',
            'oauth2_refresh_token_history', ['grant_id'], unique=False,
        )


def upgrade():
    _create_authorization_codes()
    _create_grants()
    _create_refresh_token_history()


def downgrade():
    tables = _tables()
    if 'oauth2_refresh_token_history' in tables:
        if 'ix_oauth2_refresh_token_history_grant_id' in _indexes('oauth2_refresh_token_history'):
            op.drop_index(
                'ix_oauth2_refresh_token_history_grant_id',
                table_name='oauth2_refresh_token_history',
            )
        op.drop_table('oauth2_refresh_token_history')
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
