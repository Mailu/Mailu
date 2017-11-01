""" Add a maximum quota per domain

Revision ID: 2335c80a6bc3
Revises: 12e9a4f6ed73
Create Date: 2016-12-04 12:57:37.576622

"""

# revision identifiers, used by Alembic.
revision = '2335c80a6bc3'
down_revision = '12e9a4f6ed73'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('domain', sa.Column('max_quota_bytes', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('domain') as batch:
        batch.drop_column('max_quota_bytes')
