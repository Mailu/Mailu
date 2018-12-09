""" Fix constraint naming by addint a name to all constraints

Revision ID: 546b04c886f0
Revises: 5aeb5811408e
Create Date: 2018-12-08 16:33:37.757634

"""

# revision identifiers, used by Alembic.
revision = '546b04c886f0'
down_revision = 'cd79ed46d9c2'

from alembic import op, context
import sqlalchemy as sa


def upgrade():
    # Only run this for somehow supported data types at the date we started naming constraints
    # Among others, these will probably fail on MySQL
    if context.get_bind().engine.name not in ('sqlite', 'postgresql'):
        return

    metadata = context.get_context().opts['target_metadata']

    # Drop every constraint on every table
    with op.batch_alter_table('alias', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.drop_constraint('alias_pkey', type_="primary")
        batch_op.drop_constraint('alias_domain_name_fkey', type_="foreignkey")
    with op.batch_alter_table('alternative', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.drop_constraint('alternative_pkey', type_="primary")
        batch_op.drop_constraint('alternative_domain_name_fkey', type_="foreignkey")
    with op.batch_alter_table('manager', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.drop_constraint('manager_domain_name_fkey', type_="foreignkey")
        batch_op.drop_constraint('manager_user_email_fkey', type_="foreignkey")
    with op.batch_alter_table('token', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.drop_constraint('token_pkey', type_="primary")
        batch_op.drop_constraint('token_user_email_fkey', type_="foreignkey")
    with op.batch_alter_table('fetch', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.drop_constraint('fetch_pkey', type_="primary")
        batch_op.drop_constraint('fetch_user_email_fkey', type_="foreignkey")
    with op.batch_alter_table('relay', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.drop_constraint('relay_pkey', type_="primary")
    with op.batch_alter_table('config', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.drop_constraint('config_pkey', type_="primary")
    with op.batch_alter_table('user', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.drop_constraint('user_pkey', type_="primary")
        batch_op.drop_constraint('user_domain_name_fkey', type_="foreignkey")
    with op.batch_alter_table('domain', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.drop_constraint('domain_pkey', type_="primary")

    # Recreate constraints with proper names
    with op.batch_alter_table('domain', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.create_primary_key('domain_pkey', ['name'])
    with op.batch_alter_table('alias', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.create_primary_key('alias_pkey', ['email'])
        batch_op.create_foreign_key('alias_domain_name_fkey', 'domain', ['domain_name'], ['name'])
    with op.batch_alter_table('user', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.create_primary_key('user_pkey', ['email'])
        batch_op.create_foreign_key('user_domain_name_fkey', 'domain', ['domain_name'], ['name'])
    with op.batch_alter_table('alternative', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.create_primary_key('alternative_pkey', ['name'])
        batch_op.create_foreign_key('alternative_domain_name_fkey', 'domain', ['domain_name'], ['name'])
    with op.batch_alter_table('manager', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.create_foreign_key('manager_domain_name_fkey', 'domain', ['domain_name'], ['name'])
        batch_op.create_foreign_key('manager_user_email_fkey', 'user', ['user_email'], ['email'])
    with op.batch_alter_table('token', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.create_primary_key('token_pkey', ['id'])
        batch_op.create_foreign_key('token_user_email_fkey', 'user', ['user_email'], ['email'])
    with op.batch_alter_table('fetch', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.create_primary_key('fetch_pkey', ['id'])
        batch_op.create_foreign_key('fetch_user_email_fkey', 'user', ['user_email'], ['email'])
    with op.batch_alter_table('relay', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.create_primary_key('relay_pkey', ['name'])
    with op.batch_alter_table('config', naming_convention=metadata.naming_convention) as batch_op:
        batch_op.create_primary_key('config_pkey', ['name'])


def downgrade():
    pass
