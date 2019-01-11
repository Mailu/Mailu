""" Add default columns to the configuration table

Revision ID: f1393877871d
Revises: 546b04c886f0
Create Date: 2018-12-09 16:15:42.317104

"""

# revision identifiers, used by Alembic.
revision = 'f1393877871d'
down_revision = '546b04c886f0'

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table('config') as batch_op:
        batch_op.add_column(sa.Column('comment', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('created_at', sa.Date(), nullable=False, server_default='1900-01-01'))
        batch_op.add_column(sa.Column('updated_at', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('config') as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')
        batch_op.drop_column('comment')
