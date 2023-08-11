"""Add user.change_pw_next_login

Revision ID: 0ba45693748d
Revises: 6b8f5e8caaa9
Create Date: 2023-08-10 09:20:50.458092

"""

# revision identifiers, used by Alembic.
revision = '0ba45693748d'
down_revision = '6b8f5e8caaa9'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('user', sa.Column('change_pw_next_login', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()))


def downgrade():
    op.drop_column('user', 'change_pw_next_login')
