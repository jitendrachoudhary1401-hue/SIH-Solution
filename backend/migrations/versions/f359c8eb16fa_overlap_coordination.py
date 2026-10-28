"""Human-confirmed overlap coordination groups."""
from alembic import op
import sqlalchemy as sa

revision = 'f359c8eb16fa'
down_revision = 'f248b7da05ef'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('complaint', sa.Column('incident_location', sa.String(200), nullable=False, server_default=''))
    op.create_table('coordination_group',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('primary_complaint_id', sa.Integer(), sa.ForeignKey('complaint.id'), nullable=False),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('reason', sa.String(2000), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('coordination_member',
        sa.Column('complaint_id', sa.Integer(), sa.ForeignKey('complaint.id'), primary_key=True),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('coordination_group.id'), nullable=False))
    op.create_index('ix_coordination_member_group_id', 'coordination_member', ['group_id'])
    op.create_table('case_recurrence',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('complaint_id', sa.Integer(), sa.ForeignKey('complaint.id'), nullable=False),
        sa.Column('previous_complaint_id', sa.Integer(), sa.ForeignKey('complaint.id'), nullable=False),
        sa.Column('closure_event_id', sa.Integer(), sa.ForeignKey('action_event.id'), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('previous_revision', sa.Integer(), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('complaint_id', 'previous_complaint_id', 'closure_event_id', 'revision', name='uq_recurrence_snapshot'))
    op.create_index('ix_case_recurrence_complaint_id', 'case_recurrence', ['complaint_id'])


def downgrade():
    op.drop_table('case_recurrence')
    op.drop_table('coordination_member')
    op.drop_table('coordination_group')
    op.drop_column('complaint', 'incident_location')
