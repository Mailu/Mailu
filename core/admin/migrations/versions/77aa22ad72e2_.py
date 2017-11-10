""" Add an enddate for the vacation mode

Revision ID: 77aa22ad72e2
Revises: 9400a032eb1a
Create Date: 2017-11-10 15:10:33.477592

"""

# revision identifiers, used by Alembic.
revision = '77aa22ad72e2'
down_revision = '9400a032eb1a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('user', sa.Column('reply_enddate', sa.Date(), nullable=False,
        server_default="2999-12-31"))


def downgrade():
    op.drop_column('user', 'reply_enddate')
