"""empty message

Revision ID: 8f9ea78776f4
Revises: 3b7eee912b41
Create Date: 2022-03-11 13:53:08.996055

"""

# revision identifiers, used by Alembic.
revision = '8f9ea78776f4'
down_revision = '3b7eee912b41'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('user', sa.Column('spam_mark_as_read', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()))

def downgrade():
    op.drop_column('user', 'spam_mark_as_read')
