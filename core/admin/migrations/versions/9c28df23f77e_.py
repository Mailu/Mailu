""" Set the nocase collation on the user and alias tables

Revision ID: 9c28df23f77e
Revises: c162ac88012a
Create Date: 2017-10-29 13:28:29.155754

"""

# revision identifiers, used by Alembic.
revision = '9c28df23f77e'
down_revision = 'c162ac88012a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.alter_column('email', type_=sa.String(length=255), nullable=False)
    with op.batch_alter_table('alias') as batch:
        batch.alter_column('email', type_=sa.String(length=255), nullable=False)


def downgrade():
    with op.batch_alter_table('user') as batch:
        batch.alter_column('email', type_=sa.String(length=255), nullable=False)
    with op.batch_alter_table('alias') as batch:
        batch.alter_column('email', type_=sa.String(length=255), nullable=False)
