"""Persist requested account type and organization for registration.

Revision ID: 8d42c1e7a905
Revises: 40177bd277c9
"""
from alembic import op
import sqlalchemy as sa

revision = "8d42c1e7a905"
down_revision = "40177bd277c9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch:
        batch.add_column(sa.Column("requested_role", sa.String(30), nullable=True))
        batch.add_column(sa.Column("organization", sa.String(200), nullable=True))


def downgrade():
    with op.batch_alter_table("user") as batch:
        batch.drop_column("organization")
        batch.drop_column("requested_role")
