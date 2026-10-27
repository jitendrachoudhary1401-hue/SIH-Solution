"""Mark explicitly provisioned public demo identities.

Revision ID: af4e310ce902
Revises: d72fa0981c43
"""
from alembic import op
import sqlalchemy as sa

revision = "af4e310ce902"
down_revision = "d72fa0981c43"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch:
        batch.add_column(sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table("user") as batch:
        batch.drop_column("is_demo")
