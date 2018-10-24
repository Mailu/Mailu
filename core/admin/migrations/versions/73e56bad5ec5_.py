""" Add the ability to keep forwarded messages

Revision ID: 73e56bad5ec5
Revises: 3f6994568962
Create Date: 2017-09-03 15:36:07.821002

"""

# revision identifiers, used by Alembic.
revision = '73e56bad5ec5'
down_revision = '3f6994568962'

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.add_column(sa.Column('forward_keep', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()))


def downgrade():
    with op.batch_alter_table('user') as batch:
        batch.drop_column('forward_keep')
