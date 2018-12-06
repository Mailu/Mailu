"""spam_threshold in percent

Revision ID: 27ae2f102682
Revises: dc8c25cf5b98
Create Date: 2016-09-30 08:06:15.025190

"""

# revision identifiers, used by Alembic.
revision = '27ae2f102682'
down_revision = 'dc8c25cf5b98'

from alembic import op
import sqlalchemy as sa


user_table = sa.Table(
    'user',
    sa.MetaData(),
    sa.Column('email', sa.String(255), primary_key=True),
    sa.Column('spam_threshold', sa.Numeric())
)


def upgrade():
    connection = op.get_bind()
    # spam_threshold is a X/15 based value, we're converting it to percent.
    for user in connection.execute(user_table.select()):
         connection.execute(
            user_table.update().where(
                user_table.c.email == user.email
            ).values(
                spam_threshold=int(100. * float(user.spam_threshold or 0.) / 15.)
            )
         )
    # set default to 80%
    with op.batch_alter_table('user') as batch:
        batch.alter_column('spam_threshold', server_default="80.")

def downgrade():
    connection = op.get_bind()
    # spam_threshold is a X/15 based value, we're converting it from percent.
    for user in connection.execute(user_table.select()):
         connection.execute(
            user_table.update().where(
                user_table.c.email == user.email
            ).values(
                spam_threshold=int(15. * float(user.spam_threshold or 0.) / 100.)
            )
         )
    # set default to 10/15
    with op.batch_alter_table('user') as batch:
        batch.alter_column('spam_threshold', server_default="10.")
