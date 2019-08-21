""" Add a configuration table

Revision ID: cd79ed46d9c2
Revises: 25fd6c7bcb4a
Create Date: 2018-10-17 21:44:48.924921

"""

revision = 'cd79ed46d9c2'
down_revision = '3b281286c7bd'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('config',
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('value', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('name', name=op.f('config_pkey'))
    )


def downgrade():
    op.drop_table('config')
