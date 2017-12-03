""" Enable signup per domain

Revision ID: 423155f8fc15
Revises: 77aa22ad72e2
Create Date: 2017-12-02 15:07:40.052320

"""

# revision identifiers, used by Alembic.
revision = '423155f8fc15'
down_revision = '77aa22ad72e2'

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table('domain') as batch:
        batch.add_column(sa.Column('signup_enabled', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()))


def downgrade():
    with op.batch_alter_table('domain') as batch:
        batch.drop_column('signup_enabled')
