"""Add branch database changes for replies and passkeys.

Revision ID: a72c1b9d4e6f
Revises: a8c190d4e72b
"""

from alembic import op
import sqlalchemy as sa


revision = 'a72c1b9d4e6f'
down_revision = 'a8c190d4e72b'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('reply_body_html', sa.Text(), nullable=True))
    op.add_column('passkey', sa.Column('user_verified', sa.Boolean(), nullable=True))
    op.add_column('passkey', sa.Column('credential_device_type', sa.String(length=16), nullable=True))
    op.add_column('passkey', sa.Column('backed_up', sa.Boolean(), nullable=True))
    op.add_column('passkey', sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('domain', sa.Column('passkey_enforce_aaguid', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE domain SET passkey_enforce_aaguid = TRUE WHERE trim(passkey_aaguids) <> ''")
    op.add_column('domain', sa.Column('passkey_backup_eligible_policy', sa.String(length=8), nullable=False, server_default='optional'))
    op.add_column('domain', sa.Column('passkey_backup_state_policy', sa.String(length=8), nullable=False, server_default='optional'))
    op.add_column('domain', sa.Column('passkey_require_sign_count_increase', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('domain', sa.Column('passkey_attestation_policy', sa.String(length=8), nullable=False, server_default='optional'))
    op.add_column('passkey', sa.Column('user_present', sa.Boolean(), nullable=True))
    op.add_column('passkey', sa.Column('backup_eligible', sa.Boolean(), nullable=True))
    op.add_column('passkey', sa.Column('attestation_format', sa.String(length=32), nullable=True))


def downgrade():
    op.drop_column('passkey', 'attestation_format')
    op.drop_column('passkey', 'backup_eligible')
    op.drop_column('passkey', 'user_present')
    op.drop_column('domain', 'passkey_attestation_policy')
    op.drop_column('domain', 'passkey_enforce_aaguid')
    op.drop_column('domain', 'passkey_require_sign_count_increase')
    op.drop_column('domain', 'passkey_backup_state_policy')
    op.drop_column('domain', 'passkey_backup_eligible_policy')
    op.drop_column('passkey', 'last_used_at')
    op.drop_column('passkey', 'backed_up')
    op.drop_column('passkey', 'credential_device_type')
    op.drop_column('passkey', 'user_verified')
    with op.batch_alter_table('user') as batch:
        batch.drop_column('reply_body_html')
