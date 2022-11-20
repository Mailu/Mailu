"""empty message

Revision ID: 7ac252f2bbbf
Revises: 8f9ea78776f4
Create Date: 2022-11-20 08:57:16.879152

"""

# revision identifiers, used by Alembic.
revision = '7ac252f2bbbf'
down_revision = '8f9ea78776f4'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('user', sa.Column('allow_spoofing', sa.Boolean(), nullable=False))


def downgrade():
    op.drop_column('user', 'allow_spoofing')
