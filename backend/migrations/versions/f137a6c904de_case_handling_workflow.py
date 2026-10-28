"""Case-bound handling teams, reports and appeal cycles. Existing cases are preserved."""
from alembic import op
import sqlalchemy as sa

revision = "f137a6c904de"
down_revision = "e9c54a830bf1"
branch_labels = None
depends_on = None


def upgrade():
    members = [sa.Column(role + '_id', sa.Integer(), sa.ForeignKey('user.id'))
               for role in ('faculty_reviewer', 'officer', 'lead', 'committee', 'reviewer', 'verifier', 'auditor', 'executive')]
    op.create_table('case_workflow',
        sa.Column('complaint_id', sa.Integer(), sa.ForeignKey('complaint.id'), primary_key=True),
        sa.Column('stage', sa.String(30), nullable=False),
        sa.Column('cycle', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        *members,
        sa.Column('access_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('auditor_required', sa.Boolean(), nullable=False),
        sa.Column('outcome', sa.String(30)),
        sa.Column('public_decision', sa.Text(), nullable=False),
        sa.CheckConstraint("stage IN ('initial_review','officer_triage','committee_review','investigation','executive_decision','resolved','appeal_review')"))
    op.create_table('case_workflow_report',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('complaint_id', sa.Integer(), sa.ForeignKey('case_workflow.complaint_id'), nullable=False),
        sa.Column('cycle', sa.Integer(), nullable=False),
        sa.Column('stage', sa.String(30), nullable=False),
        sa.Column('role', sa.String(30), nullable=False),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('report', sa.Text(), nullable=False),
        sa.Column('evidence_ids', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_case_workflow_report_complaint_id', 'case_workflow_report', ['complaint_id'])


def downgrade():
    op.drop_table('case_workflow_report')
    op.drop_table('case_workflow')
