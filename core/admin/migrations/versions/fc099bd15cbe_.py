"""change default unlimited value for max_users and max_aliases to -1

Revision ID: fc099bd15cbe
Revises: 5aeb5811408e
Create Date: 2019-01-06 13:40:23.372373

"""

# revision identifiers, used by Alembic.
revision = 'fc099bd15cbe'
down_revision = '5aeb5811408e'

from alembic import op
import sqlalchemy as sa


domain_table = sa.Table(
    'domain',
    sa.MetaData(),
    sa.Column('max_users', sa.Integer(), nullable=False),
    sa.Column('max_aliases', sa.Integer(), nullable=False),
)


def upgrade():
    connection = op.get_bind()
    connection.execute(
            domain_table.update().where(
                domain_table.c.max_users == 0
                ).values(
                    max_users=-1
                )
            )
    connection.execute(
            domain_table.update().where(
                domain_table.c.max_aliases == 0
                ).values(
                    max_aliases=-1
                )
            )
    #set new unlimited default to -1
    with op.batch_alter_table('domain') as batch:
        batch.alter_column('max_users', server_default='-1')
        batch.alter_column('max_aliases', server_default='-1')

def downgrade():
    connection = op.get_bind()
    connection.execute(
            domain_table.update().where(
                domain_table.c.max_users == -1
                ).values(
                    max_users=0
                )
            )
    connection.execute(
            domain_table.update().where(
                domain_table.c.max_aliases == -1
                ).values(
                    max_aliases=0
                )
            )
    #set default to 0
    with op.batch_alter_table('domain') as batch:
        batch.alter_column('max_users', server_default='0')
        batch.alter_column('max_aliases', server_default='0')
