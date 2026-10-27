"""Add expiring single-use password reset tokens.

Revision ID: d72fa0981c43
Revises: 61b37e20a4f8
"""
from alembic import op
import sqlalchemy as sa

revision = "d72fa0981c43"
down_revision = "61b37e20a4f8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("password_reset",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)))
    op.create_index("ix_password_reset_user_id", "password_reset", ["user_id"])


def downgrade():
    op.drop_index("ix_password_reset_user_id", table_name="password_reset")
    op.drop_table("password_reset")
