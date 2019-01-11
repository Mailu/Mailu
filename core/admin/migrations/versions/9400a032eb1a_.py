""" Add authentication tokens

Revision ID: 9400a032eb1a
Revises: 9c28df23f77e
Create Date: 2017-10-29 14:31:58.032989

"""

# revision identifiers, used by Alembic.
revision = '9400a032eb1a'
down_revision = '9c28df23f77e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('token',
    sa.Column('created_at', sa.Date(), nullable=False),
    sa.Column('updated_at', sa.Date(), nullable=True),
    sa.Column('comment', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_email', sa.String(length=255), nullable=False),
    sa.Column('password', sa.String(length=255), nullable=False),
    sa.Column('ip', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['user_email'], ['user.email'], name=op.f('token_user_email_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('token_pkey'))
    )


def downgrade():
    op.drop_table('token')
