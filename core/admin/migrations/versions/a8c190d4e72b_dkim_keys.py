"""Store DKIM signing keys and retirement status.

Revision ID: a8c190d4e72b
Revises: d73b4f1c8e20
Create Date: 2026-10-03
"""

from alembic import op
import sqlalchemy as sa


revision = 'a8c190d4e72b'
down_revision = 'd73b4f1c8e20'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'dkim_key',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.Date(), nullable=True),
        sa.Column('comment', sa.String(255), nullable=True),
        sa.Column('domain_name', sa.String(80), sa.ForeignKey('domain.name', ondelete='CASCADE'), nullable=False),
        sa.Column('selector', sa.String(32), nullable=False),
        sa.Column('algorithm', sa.String(16), nullable=False, server_default='rsa'),
        sa.Column('private_key', sa.LargeBinary(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('retired', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint('domain_name', 'selector'),
    )
    op.create_index('ix_dkim_key_domain_name', 'dkim_key', ['domain_name'])


def downgrade():
    op.drop_index('ix_dkim_key_domain_name', table_name='dkim_key')
    op.drop_table('dkim_key')
