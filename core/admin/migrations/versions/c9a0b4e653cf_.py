""" Add alternative domains

Revision ID: c9a0b4e653cf
Revises: 73e56bad5ec5
Create Date: 2017-09-03 18:23:36.356527

"""

# revision identifiers, used by Alembic.
revision = 'c9a0b4e653cf'
down_revision = '73e56bad5ec5'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('alternative',
    sa.Column('created_at', sa.Date(), nullable=False),
    sa.Column('updated_at', sa.Date(), nullable=True),
    sa.Column('comment', sa.String(length=255), nullable=True),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('domain_name', sa.String(length=80), nullable=True),
    sa.ForeignKeyConstraint(['domain_name'], ['domain.name'], name=op.f('alternative_domain_name_fkey')),
    sa.PrimaryKeyConstraint('name', name=op.f('alternative_pkey'))
    )


def downgrade():
    op.drop_table('alternative')
