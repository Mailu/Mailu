""" Add enabled flag to user model

Revision ID: 49d77a93118e
Revises: 423155f8fc15
Create Date: 2018-04-15 11:17:32.306088

"""

# revision identifiers, used by Alembic.
revision = '49d77a93118e'
down_revision = '423155f8fc15'

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.add_column(sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()))


def downgrade():
    with op.batch_alter_table('user') as batch:
        batch.drop_column('user', 'enabled')
