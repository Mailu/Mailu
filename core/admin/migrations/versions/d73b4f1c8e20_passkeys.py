"""Add WebAuthn passkeys and domain policy.

Revision ID: d73b4f1c8e20
Revises: 4e6b8a1c2d3f
"""

from alembic import op
import sqlalchemy as sa


revision = 'd73b4f1c8e20'
down_revision = '4e6b8a1c2d3f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('domain', sa.Column(
        'passkey_aaguid_mode', sa.String(length=8), nullable=False,
        server_default='allow',
    ))
    op.add_column('domain', sa.Column(
        'passkey_aaguids', sa.Text(), nullable=False, server_default='',
    ))
    op.add_column('domain', sa.Column(
        'passkey_require_uv', sa.Boolean(), nullable=False, server_default=sa.true(),
    ))
    op.add_column('domain', sa.Column(
        'passkey_device_bound', sa.Boolean(), nullable=False, server_default=sa.false(),
    ))
    op.add_column('domain', sa.Column(
        'passkey_resident_key', sa.String(length=16), nullable=False,
        server_default='preferred',
    ))
    op.create_table(
        'passkey',
        sa.Column('created_at', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.Date(), nullable=True),
        sa.Column('comment', sa.String(length=255), nullable=True),
        sa.Column('credential_id', sa.LargeBinary(length=1023), nullable=False),
        sa.Column('user_email', sa.String(length=255), nullable=False),
        sa.Column('public_key', sa.LargeBinary(), nullable=False),
        sa.Column('sign_count', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('aaguid', sa.String(length=36), nullable=False),
        sa.Column('device_bound', sa.Boolean(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False, server_default=''),
        sa.ForeignKeyConstraint(['user_email'], ['user.email'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('credential_id'),
    )
    op.create_index('ix_passkey_user_email', 'passkey', ['user_email'])


def downgrade():
    op.drop_index('ix_passkey_user_email', table_name='passkey')
    op.drop_table('passkey')
    op.drop_column('domain', 'passkey_resident_key')
    op.drop_column('domain', 'passkey_device_bound')
    op.drop_column('domain', 'passkey_require_uv')
    op.drop_column('domain', 'passkey_aaguids')
    op.drop_column('domain', 'passkey_aaguid_mode')
