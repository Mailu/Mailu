""" Convert all domains and emails to lowercase

Revision ID: 5aeb5811408e
Revises: cd79ed46d9c2
Create Date: 2018-12-06 16:07:23.380579

"""

# revision identifiers, used by Alembic.
revision = '5aeb5811408e'
down_revision = 'f1393877871d'

from alembic import op, config
import sqlalchemy as sa


name_column = lambda: sa.Column('name', sa.String(80), primary_key=True)
domain_name_column = lambda: sa.Column('domain_name', sa.String(80))
user_email_column = lambda: sa.Column('user_email', sa.String(255))
email_columns = lambda: [
    sa.Column('email', sa.String(255), primary_key=True),
    sa.Column('localpart', sa.String(80)),
    domain_name_column()
]
id_columns = lambda: [
    sa.Column('id', sa.Integer(), primary_key=True),
    user_email_column()
]


domain_table = sa.Table('domain', sa.MetaData(), name_column())
relay_table = sa.Table('relay', sa.MetaData(), name_column())
alternative_table = sa.Table('alternative', sa.MetaData(), name_column(), domain_name_column())
user_table = sa.Table('user', sa.MetaData(), *email_columns())
alias_table = sa.Table('alias', sa.MetaData(), *email_columns())
fetch_table = sa.Table('fetch', sa.MetaData(), *id_columns())
token_table = sa.Table('token', sa.MetaData(), *id_columns())
manager_table = sa.Table('manager', sa.MetaData(), domain_name_column(), user_email_column())


def upgrade():
    connection = op.get_bind()

    # drop foreign key constraints
    with op.batch_alter_table('alias') as batch_op:
        batch_op.drop_constraint('alias_domain_name_fkey', type_='foreignkey')
    with op.batch_alter_table('alternative') as batch_op:
        batch_op.drop_constraint('alternative_domain_name_fkey', type_='foreignkey')
    with op.batch_alter_table('manager') as batch_op:
        batch_op.drop_constraint('manager_domain_name_fkey', type_='foreignkey')
        batch_op.drop_constraint('manager_user_email_fkey', type_='foreignkey')
    with op.batch_alter_table('token') as batch_op:
        batch_op.drop_constraint('token_user_email_fkey', type_='foreignkey')
    with op.batch_alter_table('fetch') as batch_op:
        batch_op.drop_constraint('fetch_user_email_fkey', type_='foreignkey')
    with op.batch_alter_table('user') as batch_op:
        batch_op.drop_constraint('user_domain_name_fkey', type_='foreignkey')

    # lower domain names
    for domain in connection.execute(domain_table.select()):
        connection.execute(domain_table.update().where(
            domain_table.c.name == domain.name
        ).values(
            name=domain.name.lower()
        ))
    # lower alternatives
    for alternative in connection.execute(alternative_table.select()):
        connection.execute(alternative_table.update().where(
            alternative_table.c.name == alternative.name
        ).values(
            name=alternative.name.lower(),
            domain_name=alternative.domain_name.lower()
        ))
    # lower users
    for user in connection.execute(user_table.select()):
        connection.execute(user_table.update().where(
            user_table.c.email == user.email
        ).values(
            email=user.email.lower(),
            localpart=user.localpart.lower(),
            domain_name=user.domain_name.lower()
        ))
    # lower aliases
    for alias in connection.execute(alias_table.select()):
        connection.execute(alias_table.update().where(
            alias_table.c.email == alias.email
        ).values(
            email=alias.email.lower(),
            localpart=alias.localpart.lower(),
            domain_name=alias.domain_name.lower()
        ))
    # lower fetches
    for fetch in connection.execute(fetch_table.select()):
        connection.execute(fetch_table.update().where(
            fetch_table.c.id == fetch.id
        ).values(
            user_email=fetch.user_email.lower()
        ))
    # lower tokens
    for token in connection.execute(token_table.select()):
        connection.execute(token_table.update().where(
            token_table.c.id == token.id
        ).values(
            user_email=token.user_email.lower()
        ))
    # lower relays
    for relay in connection.execute(relay_table.select()):
        connection.execute(relay_table.update().where(
            relay_table.c.name == relay.name
        ).values(
            name=relay.name.lower()
        ))
    # lower managers
    for manager in connection.execute(manager_table.select()):
        connection.execute(manager_table.update().where(
            sa.and_(
                manager_table.c.domain_name == manager.domain_name,
                manager_table.c.user_email == manager.user_email
            )
        ).values(
            domain_name=manager.domain_name.lower(),
            user_email=manager.user_email.lower()
        ))

    # restore foreign key constraints
    with op.batch_alter_table('alias') as batch_op:
        batch_op.create_foreign_key('alias_domain_name_fkey', 'domain', ['domain_name'], ['name'])
    with op.batch_alter_table('user') as batch_op:
        batch_op.create_foreign_key('user_domain_name_fkey', 'domain', ['domain_name'], ['name'])
    with op.batch_alter_table('alternative') as batch_op:
        batch_op.create_foreign_key('alternative_domain_name_fkey', 'domain', ['domain_name'], ['name'])
    with op.batch_alter_table('manager') as batch_op:
        batch_op.create_foreign_key('manager_domain_name_fkey', 'domain', ['domain_name'], ['name'])
        batch_op.create_foreign_key('manager_user_email_fkey', 'user', ['user_email'], ['email'])
    with op.batch_alter_table('token') as batch_op:
        batch_op.create_foreign_key('token_user_email_fkey', 'user', ['user_email'], ['email'])
    with op.batch_alter_table('fetch') as batch_op:
        batch_op.create_foreign_key('fetch_user_email_fkey', 'user', ['user_email'], ['email'])


def downgrade():
    pass
