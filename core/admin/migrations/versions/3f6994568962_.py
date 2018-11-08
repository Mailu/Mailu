""" Add keep as an option in fetches

Revision ID: 3f6994568962
Revises: 2335c80a6bc3
Create Date: 2017-02-02 22:31:00.719703

"""

# revision identifiers, used by Alembic.
revision = '3f6994568962'
down_revision = '2335c80a6bc3'

from alembic import op
import sqlalchemy as sa


fetch_table = sa.Table(
    'fetch',
    sa.MetaData(),
    sa.Column('keep', sa.Boolean())
)


def upgrade():
    op.add_column('fetch', sa.Column('keep', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()))


def downgrade():
    with op.batch_alter_table('fetch') as batch:
        batch.drop_column('keep')
