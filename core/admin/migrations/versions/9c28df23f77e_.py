""" Set the nocase collation on the user and alias tables

Revision ID: 9c28df23f77e
Revises: c162ac88012a
Create Date: 2017-10-29 13:28:29.155754

"""

# revision identifiers, used by Alembic.
revision = '9c28df23f77e'
down_revision = 'c162ac88012a'

from alembic import op
import sqlalchemy as sa
from flask import current_app as app
from citext import CIText

def upgrade():
    if app.config['DB_FLAVOR'] == "postgresql":
        email_type = CIText()
        with op.batch_alter_table('fetch') as batch:
            batch.drop_constraint('fetch_user_email_fkey')
        with op.batch_alter_table('manager') as batch:
            batch.drop_constraint('manager_user_email_fkey')
    else:
        email_type = sa.String(length=255, collation="NOCASE")

    with op.batch_alter_table('user') as batch:
        batch.alter_column('email', type_=email_type)
    with op.batch_alter_table('alias') as batch:
        batch.alter_column('email', type_=email_type)
    with op.batch_alter_table('fetch') as batch:
        batch.alter_column('user_email', type_=email_type)
        if app.config['DB_FLAVOR'] == "postgresql":
            batch.create_foreign_key("fetch_user_email_fkey", "user", ["user_email"], ["email"])
    with op.batch_alter_table('manager') as batch:
        batch.alter_column('user_email', type_=email_type)
        if app.config['DB_FLAVOR'] == "postgresql":
            batch.create_foreign_key("manager_user_email_fkey", "user", ["user_email"], ["email"])


def downgrade():
    with op.batch_alter_table('user') as batch:
        batch.alter_column('email', type_=sa.String(length=255))
    with op.batch_alter_table('alias') as batch:
        batch.alter_column('email', type_=sa.String(length=255))
