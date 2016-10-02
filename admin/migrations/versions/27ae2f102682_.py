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

from freeposte.admin.models import User
from freeposte import db

def upgrade():
    # spam_threshold is a X/15 based value, we're converting it to percent.
    for user in User.query.all():
         user.spam_threshold = int(100. * float(user.spam_threshold or 0.) / 15.)
    db.session.commit()

    # set default to 80%
    with op.batch_alter_table('user') as batch:
        batch.alter_column('spam_threshold', default=80.)

def downgrade():
    # spam_threshold is a X/15 based value, we're converting it from percent.
    for user in User.query.all():
         user.spam_threshold = int(15. * float(user.spam_threshold or 0.) / 100.)
    db.session.commit()

    # set default to 10/15
    with op.batch_alter_table('user') as batch:
        batch.alter_column('spam_threshold', default=10.)
