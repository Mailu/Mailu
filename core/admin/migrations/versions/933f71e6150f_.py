"""empty message

Revision ID: 933f71e6150f
Revises: 0ba45693748d
Create Date: 2025-09-27 19:23:43.899566

"""

# revision identifiers, used by Alembic.
revision = '933f71e6150f'
down_revision = '0ba45693748d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('fetch', sa.Column('invisible', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()))


def downgrade():
    op.drop_column('fetch', 'invisible')
