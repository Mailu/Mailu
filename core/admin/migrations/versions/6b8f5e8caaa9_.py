"""Enlarge token.ip

Revision ID: 6b8f5e8caaa9
Revises: 7ac252f2bbbf
Create Date: 2023-06-08 11:35:43.477708

"""

# revision identifiers, used by Alembic.
revision = '6b8f5e8caaa9'
down_revision = '7ac252f2bbbf'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('token', 'ip',
               existing_type=sa.String(),
               type=sa.VARCHAR(length=4096),
               existing_nullable=True)

def downgrade():
    pass
