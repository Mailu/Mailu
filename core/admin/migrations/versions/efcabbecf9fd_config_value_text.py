"""Store configuration values without a length limit."""
from alembic import op
import sqlalchemy as sa

revision = "efcabbecf9fd"
down_revision = "da2450b982af"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("config") as batch:
        batch.alter_column("value", existing_type=sa.String(255), type_=sa.Text())


def downgrade():
    with op.batch_alter_table("config") as batch:
        batch.alter_column("value", existing_type=sa.Text(), type_=sa.String(255))
