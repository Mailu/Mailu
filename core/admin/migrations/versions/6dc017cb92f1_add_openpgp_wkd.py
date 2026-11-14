"""Add OpenPGP keys and WKD address mappings

Revision ID: 6dc017cb92f1
Revises: 9a5866105f5a
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa


revision = '6dc017cb92f1'
down_revision = '9a5866105f5a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('gpg_key', sa.Text(), nullable=True))
    op.create_table(
        'wkd_key',
        sa.Column('key_hash', sa.String(length=32), nullable=False),
        sa.Column('domain_name', sa.String(length=80), nullable=False),
        sa.Column('user_email', sa.String(length=255), nullable=False),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('key_data', sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(
            ['user_email'], ['user.email'],
            name='wkd_key_user_email_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint(
            'key_hash', 'domain_name', 'user_email', 'fingerprint', name='wkd_key_pkey'),
    )


def downgrade():
    op.drop_table('wkd_key')
    op.drop_column('user', 'gpg_key')
