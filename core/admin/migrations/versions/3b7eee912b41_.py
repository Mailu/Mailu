"""change quota type to bigint

Revision ID: 3b7eee912b41
Revises: fc099bd15cbe
Create Date: 2019-01-15 08:51:05.346257

"""

# revision identifiers, used by Alembic.
revision = '3b7eee912b41'
down_revision = 'fc099bd15cbe'

from alembic import op
import sqlalchemy as sa

def upgrade():
    with op.batch_alter_table('domain') as batch:
        batch.alter_column('max_quota_bytes', type_=sa.BigInteger(), nullable=False, server_default='0')

    with op.batch_alter_table('user') as batch:
        batch.alter_column('quota_bytes', type_=sa.BigInteger(), nullable=False)
        batch.alter_column('quota_bytes_used', type_=sa.BigInteger(), nullable=False, server_default='0')

def downgrade():
    with op.batch_alter_table('domain') as batch:
        batch.alter_column('max_quota_bytes', type_=sa.Integer(), nullable=False, server_default='0')

    with op.batch_alter_table('user') as batch:
        batch.alter_column('quota_bytes', type_=sa.Integer(), nullable=False)
        batch.alter_column('quota_bytes_used', type_=sa.Integer(), nullable=False, server_default='0')
