""" Initial schema

Revision ID: ff0417f4318f
Revises: None
Create Date: 2016-06-25 13:07:11.132070

"""

# revision identifiers, used by Alembic.
revision = 'ff0417f4318f'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('domain',
        sa.Column('created_at', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.Date(), nullable=True),
        sa.Column('comment', sa.String(length=255), nullable=True),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('max_users', sa.Integer(), nullable=False),
        sa.Column('max_aliases', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('name', name=op.f('domain_pkey'))
    )
    op.create_table('alias',
        sa.Column('created_at', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.Date(), nullable=True),
        sa.Column('comment', sa.String(length=255), nullable=True),
        sa.Column('localpart', sa.String(length=80), nullable=False),
        sa.Column('destination', sa.String(length=1023), nullable=False),
        sa.Column('domain_name', sa.String(length=80), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['domain_name'], ['domain.name'], name=op.f('alias_domain_name_fkey')),
        sa.PrimaryKeyConstraint('email', name=op.f('alias_pkey'))
    )
    op.create_table('user',
        sa.Column('created_at', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.Date(), nullable=True),
        sa.Column('comment', sa.String(length=255), nullable=True),
        sa.Column('localpart', sa.String(length=80), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=False),
        sa.Column('quota_bytes', sa.Integer(), nullable=False),
        sa.Column('global_admin', sa.Boolean(), nullable=False),
        sa.Column('enable_imap', sa.Boolean(), nullable=False),
        sa.Column('enable_pop', sa.Boolean(), nullable=False),
        sa.Column('forward_enabled', sa.Boolean(), nullable=False),
        sa.Column('forward_destination', sa.String(length=255), nullable=True),
        sa.Column('reply_enabled', sa.Boolean(), nullable=False),
        sa.Column('reply_subject', sa.String(length=255), nullable=True),
        sa.Column('reply_body', sa.Text(), nullable=True),
        sa.Column('displayed_name', sa.String(length=160), nullable=False),
        sa.Column('spam_enabled', sa.Boolean(), nullable=False),
        sa.Column('spam_threshold', sa.Numeric(), nullable=False),
        sa.Column('domain_name', sa.String(length=80), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['domain_name'], ['domain.name'], name=op.f('user_domain_name_fkey')),
        sa.PrimaryKeyConstraint('email', name=op.f('user_pkey'))
    )
    op.create_table('fetch',
        sa.Column('created_at', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.Date(), nullable=True),
        sa.Column('comment', sa.String(length=255), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_email', sa.String(length=255), nullable=False),
        sa.Column('protocol', sa.Enum('imap', 'pop3', name='enum_protocol'), nullable=False),
        sa.Column('host', sa.String(length=255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('tls', sa.Boolean(), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['user_email'], ['user.email'], name=op.f('fetch_user_email_fkey')),
        sa.PrimaryKeyConstraint('id', name=op.f('fetch_pkey'))
        )
    op.create_table('manager',
        sa.Column('domain_name', sa.String(length=80), nullable=True),
        sa.Column('user_email', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['domain_name'], ['domain.name'], name=op.f('manager_domain_name_fkey')),
        sa.ForeignKeyConstraint(['user_email'], ['user.email'], name=op.f('manager_user_email_fkey'))
    )


def downgrade():
    op.drop_table('manager')
    op.drop_table('fetch')
    op.drop_table('user')
    op.drop_table('alias')
    op.drop_table('domain')
