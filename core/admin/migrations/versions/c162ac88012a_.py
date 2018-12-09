""" Add relayed domains

Revision ID: c162ac88012a
Revises: c9a0b4e653cf
Create Date: 2017-09-10 20:21:10.011969

"""

# revision identifiers, used by Alembic.
revision = 'c162ac88012a'
down_revision = 'c9a0b4e653cf'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('relay',
    sa.Column('created_at', sa.Date(), nullable=False),
    sa.Column('updated_at', sa.Date(), nullable=True),
    sa.Column('comment', sa.String(length=255), nullable=True),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('smtp', sa.String(length=80), nullable=True),
    sa.PrimaryKeyConstraint('name', name=op.f('relay_pkey'))
    )


def downgrade():
    op.drop_table('relay')
