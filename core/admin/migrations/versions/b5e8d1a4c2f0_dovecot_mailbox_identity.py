"""Add a stable Dovecot uid/gid to every mailbox.

Revision ID: b5e8d1a4c2f0
Revises: ab6f4e2c91d0
"""
from alembic import op
import sqlalchemy as sa

revision = 'b5e8d1a4c2f0'
down_revision = 'ab6f4e2c91d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'domain',
        sa.Column('max_domain_quota_bytes', sa.BigInteger(), nullable=False, server_default='0'),
    )
    op.add_column('user', sa.Column('dovecot_uid', sa.Integer(), nullable=True))
    bind = op.get_bind()
    user_table = sa.table(
        'user', sa.column('email', sa.String()), sa.column('dovecot_uid', sa.Integer())
    )
    rows = bind.execute(sa.select(user_table.c.email).order_by(user_table.c.email)).fetchall()
    for offset, row in enumerate(rows):
        bind.execute(
            user_table.update().where(user_table.c.email == row[0]).values(dovecot_uid=100000 + offset)
        )
    with op.batch_alter_table('user') as batch:
        batch.alter_column('dovecot_uid', existing_type=sa.Integer(), nullable=False)
    op.create_index('user_dovecot_uid_key', 'user', ['dovecot_uid'], unique=True)
    op.create_index('ix_user_domain_name', 'user', ['domain_name'], unique=False)


def downgrade():
    op.drop_index('ix_user_domain_name', table_name='user')
    op.drop_index('user_dovecot_uid_key', table_name='user')
    op.drop_column('user', 'dovecot_uid')
    op.drop_column('domain', 'max_domain_quota_bytes')
