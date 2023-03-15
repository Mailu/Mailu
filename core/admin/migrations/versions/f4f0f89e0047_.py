""" Add fetch.scan and fetch.folders

Revision ID: f4f0f89e0047
Revises: 8f9ea78776f4
Create Date: 2022-11-13 16:29:01.246509

"""

# revision identifiers, used by Alembic.
revision = 'f4f0f89e0047'
down_revision = '8f9ea78776f4'

from alembic import op
import sqlalchemy as sa
import mailu

def upgrade():
    with op.batch_alter_table('fetch') as batch:
        batch.add_column(sa.Column('scan', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()))
        batch.add_column(sa.Column('folders', mailu.models.CommaSeparatedList(), nullable=True))

def downgrade():
    with op.batch_alter_table('fetch') as batch:
        batch.drop_column('folders')
        batch.drop_column('scan')
