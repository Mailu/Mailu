""" Update the spam threshold default value

Revision ID: a4accda8a8c7
Revises: c5696b48442d
Create Date: 2016-08-18 20:34:19.624603

"""

# revision identifiers, used by Alembic.
revision = 'a4accda8a8c7'
down_revision = 'c5696b48442d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.drop_column('spam_threshold')
        batch.add_column(sa.Column('spam_threshold', sa.Numeric(),
                         default=10.0))


def downgrade():
    pass
