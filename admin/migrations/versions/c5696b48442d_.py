""" Add wildcard aliases

Revision ID: c5696b48442d
Revises: ff0417f4318f
Create Date: 2016-08-15 22:19:50.128960

"""

# revision identifiers, used by Alembic.
revision = 'c5696b48442d'
down_revision = 'ff0417f4318f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('alias', sa.Column('wildcard', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()))


def downgrade():
    op.drop_column('alias', 'wildcard')
