""" Add avatar support to User model

Revision ID: a4e8a74b1234
Revises: f4f0f89e0047
Create Date: 2025-07-24 12:00:00.000000

"""

# revision identifiers, used by Alembic.
revision = 'a4e8a74b1234'
down_revision = 'f4f0f89e0047'

from alembic import op
import sqlalchemy as sa


def upgrade():
    """ Add avatar_filename column to user table """
    with op.batch_alter_table('user') as batch:
        batch.add_column(sa.Column('avatar_filename', sa.String(255), nullable=True))


def downgrade():
    """ Remove avatar_filename column from user table """
    with op.batch_alter_table('user') as batch:
        batch.drop_column('avatar_filename')
