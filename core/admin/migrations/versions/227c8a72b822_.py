"""Add user.change_pw_next_login

Revision ID: 227c8a72b822
Revises: 0ba45693748d
Create Date: 2023-09-23 22:20:51.458092

"""

# revision identifiers, used by Alembic.
revision = '227c8a72b822'
down_revision = '0ba45693748d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('domain', sa.Column('dkim_key', sa.String(length=4096), nullable=True))


def downgrade():
    op.drop_column('domain', 'dkim_key')
