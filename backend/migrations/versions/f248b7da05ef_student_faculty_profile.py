"""Student faculty contact and admission/pass-out years."""
from alembic import op
import sqlalchemy as sa

revision = 'f248b7da05ef'
down_revision = 'f137a6c904de'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.add_column(sa.Column('faculty_name', sa.String(150), nullable=False, server_default=''))
        batch.add_column(sa.Column('admission_year', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('passout_year', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('user') as batch:
        batch.drop_column('passout_year')
        batch.drop_column('admission_year')
        batch.drop_column('faculty_name')
