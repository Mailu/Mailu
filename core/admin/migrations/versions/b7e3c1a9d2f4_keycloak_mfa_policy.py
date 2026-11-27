"""Add per-domain and per-mailbox Keycloak two-factor policies.

NULL inherits (mailbox -> domain -> KEYCLOAK_MFA_DEFAULT), true requires
two-factor sign-in through Keycloak, false exempts.

Revision ID: b7e3c1a9d2f4
Revises: da2450b982af
"""

from alembic import op
import sqlalchemy as sa


revision = 'b7e3c1a9d2f4'
down_revision = 'da2450b982af'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('domain', sa.Column('mfa_required', sa.Boolean(), nullable=True))
    op.add_column('user', sa.Column('mfa_required', sa.Boolean(), nullable=True))


def downgrade():
    with op.batch_alter_table('user') as batch:
        batch.drop_column('mfa_required')
    with op.batch_alter_table('domain') as batch:
        batch.drop_column('mfa_required')
