"""Add a stable Dovecot uid/gid to every mailbox.

Revision ID: b5e8d1a4c2f0
Revises: ab6f4e2c91d0
"""
import logging

from alembic import op
from flask import current_app
import sqlalchemy as sa
from socrate.mailbox import RESERVED_UIDS, valid_uid

revision = 'b5e8d1a4c2f0'
down_revision = 'ab6f4e2c91d0'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # Check the range before any schema change: SQLite runs DDL outside the
    # transaction, so a later failure would leave the columns half-added and
    # every retry would fail on them.
    low, high = current_app.config['MAILBOX_UID_RANGE']
    count = bind.execute(sa.text('SELECT COUNT(*) FROM "user"')).scalar()
    usable = high - low + 1 - sum(1 for uid in RESERVED_UIDS if low <= uid <= high)
    if count > usable:
        message = (
            f'{count} mailboxes do not fit into MAILBOX_UID_MIN..MAILBOX_UID_MAX '
            f'({low}-{high}, {usable} usable IDs); widen the range'
        )
        # Flask-Migrate reports a RuntimeError through a logger that Alembic's
        # logging setup disables; log it where the migration output appears.
        logging.getLogger('alembic.runtime.migration').error(message)
        raise RuntimeError(message)
    op.add_column(
        'domain',
        sa.Column('max_domain_quota_bytes', sa.BigInteger(), nullable=False, server_default='0'),
    )
    op.add_column('user', sa.Column('dovecot_uid', sa.Integer(), nullable=True))
    user_table = sa.table(
        'user', sa.column('email', sa.String()), sa.column('dovecot_uid', sa.Integer())
    )
    rows = bind.execute(sa.select(user_table.c.email).order_by(user_table.c.email)).fetchall()
    # Number existing mailboxes from MAILBOX_UID_MIN, so that a smaller range
    # (rootless Docker/Podman, userns-remap) gets valid IDs right away.
    uids = (uid for uid in range(low, high + 1) if valid_uid(uid, low, high))
    for row, uid in zip(rows, uids):
        bind.execute(
            user_table.update().where(user_table.c.email == row[0]).values(dovecot_uid=uid)
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
