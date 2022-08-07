""" Add table for user relay

Revision ID: a30bcdbb3631
Revises: 8f9ea78776f4
Create Date: 2022-07-12 21:06:53.749360

"""

# revision identifiers, used by Alembic.
revision = 'a30bcdbb3631'
down_revision = '8f9ea78776f4'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('user_relay',
    sa.Column('created_at', sa.Date(), nullable=False),
    sa.Column('updated_at', sa.Date(), nullable=True),
    sa.Column('comment', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_email', sa.String(length=255), nullable=False),
    sa.Column('relay_mail', sa.String(length=255), nullable=False),
    sa.Column('host', sa.String(length=255), nullable=False),
    sa.Column('port', sa.Integer(), nullable=False),
    sa.Column('tls', sa.Boolean(), nullable=False),
    sa.Column('username', sa.String(length=255), nullable=False),
    sa.Column('password', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['user_email'], ['user.email'], name=op.f('user_relay_user_email_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('user_relay_pkey')),
    sa.UniqueConstraint('relay_mail')
    )


def downgrade():
    op.drop_table('user_relay')
