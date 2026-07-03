"""Add Domain.outgoing_only

Marks a domain as send-only so postfix_mailbox_domain does not resolve
it as a local mailbox domain. Used when Mailu is only responsible for
sending mail for a domain (e.g. DKIM-signing outbound) while incoming
mail is handled by another provider.

Idempotent: the ``outgoing_only`` column is only added if it does not
already exist.

Revision ID: 8b653eeb2828
Revises: fdff7f84d363
Create Date: 2023-03-28 21:25:25.879073
"""

revision = '8b653eeb2828'
down_revision = 'fdff7f84d363'

from alembic import op
import sqlalchemy as sa


def _column_exists(table, column):
    insp = sa.inspect(op.get_context().bind)
    return any(c['name'] == column for c in insp.get_columns(table))


def upgrade():
    if not _column_exists('domain', 'outgoing_only'):
        op.add_column('domain', sa.Column('outgoing_only', sa.Boolean(), nullable=True))


def downgrade():
    if _column_exists('domain', 'outgoing_only'):
        op.drop_column('domain', 'outgoing_only')
