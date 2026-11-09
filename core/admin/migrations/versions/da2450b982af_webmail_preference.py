"""Store each user's preferred webmail."""
from alembic import op
import sqlalchemy as sa

revision = "da2450b982af"
down_revision = "b5e8d1a4c2f0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("webmail_preference", sa.String(32), nullable=True))


def downgrade():
    op.drop_column("user", "webmail_preference")
