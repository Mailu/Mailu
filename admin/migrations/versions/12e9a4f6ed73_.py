"""Set the spam threshold as an integer

Revision ID: 12e9a4f6ed73
Revises: 27ae2f102682
Create Date: 2016-11-08 20:22:54.169833

"""

# revision identifiers, used by Alembic.
revision = '12e9a4f6ed73'
down_revision = '27ae2f102682'

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
    # Make sure that every value is already an Integer
    for user in connection.execute(user_table.select()):
        connection.execute(
            user_table.update().where(
                user_table.c.email == user.email
            ).values(
                spam_threshold=int(user.spam_threshold)
            )
        )
    # Migrate the table
    with op.batch_alter_table('user') as batch:
        batch.alter_column(
            'spam_threshold', existing_type=sa.Numeric(), type_=sa.Integer())


def downgrade():
    # Migrate the table
    with op.batch_alter_table('user') as batch:
        batch.alter_column(
            'spam_threshold', existing_type=sa.Integer(), type_=sa.Numeric())
