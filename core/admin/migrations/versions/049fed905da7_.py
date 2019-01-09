""" Enforce the nocase collation on the email table

Revision ID: 049fed905da7
Revises: 49d77a93118e
Create Date: 2018-04-21 13:23:56.571524

"""

# revision identifiers, used by Alembic.
revision = '049fed905da7'
down_revision = '49d77a93118e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.alter_column('email', type_=sa.String(length=255), nullable=False)


def downgrade():
    with op.batch_alter_table('user') as batch:
        batch.alter_column('email', type_=sa.String(length=255), nullable=False)

