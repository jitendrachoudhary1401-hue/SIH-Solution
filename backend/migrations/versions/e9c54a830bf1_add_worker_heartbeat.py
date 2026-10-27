"""Add safe operational worker liveness metadata."""
from alembic import op
import sqlalchemy as sa

revision = "e9c54a830bf1"
down_revision = "c7b409d2e106"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("worker_heartbeat",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("succeeded_at", sa.DateTime(timezone=True)),
        sa.Column("failed_stages", sa.JSON(), nullable=False))


def downgrade():
    op.drop_table("worker_heartbeat")
