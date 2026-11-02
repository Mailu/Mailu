"""Add allow_login column to alias table.

Revision ID: c29f4a18e72b
Revises: ea12b9426c7f
"""

from alembic import op
import sqlalchemy as sa


revision = 'c29f4a18e72b'
down_revision = 'ea12b9426c7f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'alias',
        sa.Column('allow_login', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column('alias', 'allow_login')
