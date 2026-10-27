"""Allow only one system administrator account.

Revision ID: 61b37e20a4f8
Revises: 8d42c1e7a905
"""
from alembic import op
import sqlalchemy as sa

revision = "61b37e20a4f8"
down_revision = "8d42c1e7a905"
branch_labels = None
depends_on = None


def upgrade():
    count = op.get_bind().execute(sa.text('SELECT COUNT(*) FROM "user" WHERE role = :role'), {"role": "admin"}).scalar_one()
    if count > 1:
        raise RuntimeError("Multiple administrator accounts exist. Select the single administrator account before applying this migration.")
    op.create_index("uq_single_system_administrator", "user", ["role"], unique=True,
                    postgresql_where=sa.text("role = 'admin'"), sqlite_where=sa.text("role = 'admin'"))


def downgrade():
    op.drop_index("uq_single_system_administrator", table_name="user")
