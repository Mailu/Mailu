"""Add passkey enrollment and required-enrollment policies.

Revision ID: ea12b9426c7f
Revises: a72c1b9d4e6f
"""

from alembic import op
import sqlalchemy as sa


revision = 'ea12b9426c7f'
down_revision = 'a72c1b9d4e6f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'user',
        sa.Column('passkey_enroll_next_login', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'domain',
        sa.Column('passkey_require_enrollment', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        'passkey_enrollment',
        sa.Column('created_at', sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column('updated_at', sa.Date(), nullable=True),
        sa.Column('comment', sa.String(length=255), nullable=True),
        sa.Column('token_hash', sa.String(length=64), primary_key=True),
        sa.Column('user_email', sa.String(length=255), sa.ForeignKey('user.email', ondelete='CASCADE'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_passkey_enrollment_user_email', 'passkey_enrollment', ['user_email'])


def downgrade():
    op.drop_index('ix_passkey_enrollment_user_email', table_name='passkey_enrollment')
    op.drop_table('passkey_enrollment')
    op.drop_column('domain', 'passkey_require_enrollment')
    op.drop_column('user', 'passkey_enroll_next_login')
