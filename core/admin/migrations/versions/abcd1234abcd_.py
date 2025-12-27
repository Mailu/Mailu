"""Add Anonymous Email Service (anonmail) fields and domain_access table

Revision ID: abcd1234abcd
Revises: 0ba45693748d
Create Date: 2025-12-23 00:00:00.000000

"""

# revision identifiers, used by Alembic.
revision = 'abcd1234abcd'
down_revision = '0ba45693748d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Add Anonymous Email Service columns to domain
    with op.batch_alter_table('domain') as batch:
        batch.add_column(sa.Column('anonmail_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))

    # Add Anonymous Email Service columns to alias
    with op.batch_alter_table('alias') as batch:
        batch.add_column(sa.Column('hostname', sa.String(length=255), nullable=True))
        batch.add_column(sa.Column('owner_email', sa.String(length=255), nullable=True))
        batch.create_foreign_key('alias_owner_email_fkey', 'user', ['owner_email'], ['email'])
        batch.add_column(sa.Column('disabled', sa.Boolean(), nullable=False, server_default=sa.false()))

    # Create domain_access table
    op.create_table('domain_access',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('domain_name', sa.String(length=255), nullable=False),
        sa.Column('user_email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.Date(), nullable=True),
        sa.Column('comment', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['domain_name'], ['domain.name'], name=op.f('domain_access_domain_name_fkey')),
        sa.ForeignKeyConstraint(['user_email'], ['user.email'], name=op.f('domain_access_user_email_fkey')),
        sa.PrimaryKeyConstraint('id', name=op.f('domain_access_pkey')),
        sa.UniqueConstraint('domain_name', 'user_email', name='uq_domain_access_user')
    )

    # Add token_lookup_hash for fast token authentication
    with op.batch_alter_table('token') as batch:
        batch.add_column(sa.Column('token_lookup_hash', sa.String(length=64), nullable=True))
        batch.create_index('ix_token_lookup_hash', ['token_lookup_hash'], unique=True)


def downgrade():
    # Drop token_lookup_hash
    with op.batch_alter_table('token') as batch:
        batch.drop_index('ix_token_lookup_hash')
        batch.drop_column('token_lookup_hash')

    # Drop domain_access
    op.drop_table('domain_access')

    # Drop columns from alias
    with op.batch_alter_table('alias') as batch:
        batch.drop_column('disabled')
        batch.drop_constraint('alias_owner_email_fkey', type_='foreignkey')
        batch.drop_column('owner_email')
        batch.drop_column('hostname')

    # Drop columns from domain
    with op.batch_alter_table('domain') as batch:
        batch.drop_column('anonmail_enabled')
