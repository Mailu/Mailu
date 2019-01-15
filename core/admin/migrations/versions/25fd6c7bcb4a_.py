""" Add a column for used quota

Revision ID: 25fd6c7bcb4a
Revises: 049fed905da7
Create Date: 2018-07-25 21:56:09.729153

"""

# revision identifiers, used by Alembic.
revision = '25fd6c7bcb4a'
down_revision = '049fed905da7'

from alembic import op
import sqlalchemy as sa


from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.add_column(sa.Column('quota_bytes_used', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('user') as batch:
        batch.drop_column('user', 'quota_bytes_used')
