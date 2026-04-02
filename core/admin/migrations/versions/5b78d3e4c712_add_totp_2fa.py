"""Add TOTP two-factor authentication

Revision ID: 5b78d3e4c712
Revises: 0ba45693748d
Create Date: 2026-04-02 12:00:00.000000

"""

# revision identifiers, used by Alembic.
revision = '5b78d3e4c712'
down_revision = '0ba45693748d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # add TOTP columns to user table
    with op.batch_alter_table('user') as batch:
        batch.add_column(sa.Column('totp_secret', sa.String(255), nullable=True))
        batch.add_column(sa.Column('totp_enabled', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()))

    # create backup_code table
    op.create_table('backup_code',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_email', sa.String(255), sa.ForeignKey('user.email'), nullable=False),
        sa.Column('code_hash', sa.String(255), nullable=False),
        sa.Column('comment', sa.String(255), nullable=True),
        sa.Column('created_at', sa.Date(), nullable=True),
        sa.Column('updated_at', sa.Date(), nullable=True),
    )


def downgrade():
    op.drop_table('backup_code')

    with op.batch_alter_table('user') as batch:
        batch.drop_column('totp_enabled')
        batch.drop_column('totp_secret')
