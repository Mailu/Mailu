"""Add inherited Base columns to WKD keys

Revision ID: 4e6b8a1c2d3f
Revises: 6dc017cb92f1
Create Date: 2026-10-09
"""

from alembic import op
import sqlalchemy as sa


revision = '4e6b8a1c2d3f'
down_revision = '6dc017cb92f1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('wkd_key') as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.Date(), nullable=False,
                                      server_default='1900-01-01'))
        batch_op.add_column(sa.Column('updated_at', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('comment', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('wkd_key') as batch_op:
        batch_op.drop_column('comment')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')
