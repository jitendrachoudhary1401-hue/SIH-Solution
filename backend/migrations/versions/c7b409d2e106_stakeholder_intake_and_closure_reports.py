"""Stakeholder ownership, retry-safe evidence and immutable closure PDFs."""
from alembic import op
import sqlalchemy as sa

revision = 'c7b409d2e106'
down_revision = 'af4e310ce902'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('complaint') as batch:
        batch.add_column(sa.Column('submitter_user_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_complaint_submitter_user_id_user', 'user', ['submitter_user_id'], ['id'])
        batch.create_index('ix_complaint_submitter_user_id', ['submitter_user_id'])
    with op.batch_alter_table('attachment') as batch:
        batch.add_column(sa.Column('uploaded_by', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('upload_key', sa.String(100), nullable=True))
        batch.create_foreign_key('fk_attachment_uploaded_by_user', 'user', ['uploaded_by'], ['id'])
        batch.create_unique_constraint('uq_attachment_complaint_upload_key', ['complaint_id', 'upload_key'])
    op.create_table('complaint_report',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('complaint_id', sa.Integer(), sa.ForeignKey('complaint.id'), nullable=False),
        sa.Column('closure_event_id', sa.Integer(), sa.ForeignKey('action_event.id'), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('pdf', sa.LargeBinary(), nullable=False),
        sa.Column('checksum', sa.String(64), nullable=False))
    op.create_index('ix_complaint_report_complaint_id', 'complaint_report', ['complaint_id'])


def downgrade():
    op.drop_table('complaint_report')
    with op.batch_alter_table('attachment') as batch:
        batch.drop_constraint('uq_attachment_complaint_upload_key', type_='unique')
        batch.drop_constraint('fk_attachment_uploaded_by_user', type_='foreignkey')
        batch.drop_column('upload_key')
        batch.drop_column('uploaded_by')
    with op.batch_alter_table('complaint') as batch:
        batch.drop_index('ix_complaint_submitter_user_id')
        batch.drop_constraint('fk_complaint_submitter_user_id_user', type_='foreignkey')
        batch.drop_column('submitter_user_id')
