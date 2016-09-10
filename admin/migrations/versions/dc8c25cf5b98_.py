""" Add metadata related to fetches

Revision ID: dc8c25cf5b98
Revises: a4accda8a8c7
Create Date: 2016-09-10 12:41:01.161357

"""

# revision identifiers, used by Alembic.
revision = 'dc8c25cf5b98'
down_revision = 'a4accda8a8c7'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('fetch', sa.Column('error', sa.String(length=1023), nullable=True))
    op.add_column('fetch', sa.Column('last_check', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('fetch') as batch:
        batch.drop_column('last_check')
        batch.drop_column('error')
