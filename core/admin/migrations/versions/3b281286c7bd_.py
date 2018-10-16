""" Add a start day for vacations

Revision ID: 3b281286c7bd
Revises: 25fd6c7bcb4a
Create Date: 2018-09-27 22:20:08.158553

"""

revision = '3b281286c7bd'
down_revision = '25fd6c7bcb4a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.add_column(sa.Column('reply_startdate', sa.Date(), nullable=False,
            server_default="1900-01-01"))


def downgrade():
    with op.batch_alter_table('user') as batch:
        batch.drop_column('reply_startdate')
