""" Add an password complexity into domain table
Revision ID: 0242ac120002
Revises: 3b7eee912b41
Create Date: 2022-01-28 17:10:22.477592
"""

# revision identifiers, used by Alembic.
revision = '0242ac120002'
down_revision = '3b7eee912b41'

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table('domain') as batch:
        batch.add_column(sa.Column('password_complexity_enabled', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()))


def downgrade():
    with op.batch_alter_table('domain') as batch:
        batch.drop_column('password_complexity_enabled')