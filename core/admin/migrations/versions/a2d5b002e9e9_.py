"""Add alias delegation API support to domains

Revision ID: a2d5b002e9e9
Revises: 3b7eee912b41
Create Date: 2022-05-10 14:53:36.720346

"""

# revision identifiers, used by Alembic.
revision = 'a2d5b002e9e9'
down_revision = '3b7eee912b41'

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table('domain') as batch:
        batch.add_column(sa.Column('alias_delegation_api', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('domain') as batch:
        batch.drop_column('alias_delegation_api')
