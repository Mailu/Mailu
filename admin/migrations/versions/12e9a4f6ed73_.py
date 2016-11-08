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

from mailu.admin import models
from mailu import db


def upgrade():
    # Make sure that every value is already an Integer
    for user in models.User.query.all():
         user.spam_threshold = int(user.spam_threshold)
    db.session.commit()
    # Migrate the table
    with op.batch_alter_table('user') as batch:
        batch.alter_column(
            'spam_threshold', existing_type=db.Numeric(), type_=db.Integer())


def downgrade():
    # Migrate the table
    with op.batch_alter_table('user') as batch:
        batch.alter_column(
            'spam_threshold', existing_type=db.Integer(), type_=db.Numeric())
